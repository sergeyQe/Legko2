"""Сервис редактора: загрузка потоков, действия над черновиком, предпросмотр и отправка в Keitaro."""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import draft as draft_ops
from app.domain.errors import WeightError
from app.domain.merge import merge_with_keitaro
from app.domain.states import DraftOffer, KtOfferState, active_sum, offer_state
from app.keitaro.client import KeitaroClient
from app.keitaro.models import CatalogOffer, KtStream, PushOffer
from app.models import Campaign, Stream
from app.models.mapping import stream_to_drafts, sync_stream_offers
from app.services.errors import EntityNotFoundError, MergeConflictError
from app.services.views import CampaignSummary, CampaignView, OfferView, PreviewView, StreamView

logger = logging.getLogger(__name__)


class EditorService:
    """Работает с одной сессией БД и одним клиентом Keitaro.

    Правило сохранения: записи БД меняются только после успешной доменной операции и (для Push) после
    успешного ответа Keitaro. Поэтому при любой ошибке черновик остаётся как был.
    """

    def __init__(self, session: Session, keitaro: KeitaroClient) -> None:
        self._session = session
        self._keitaro = keitaro

    # ---------- кампании и загрузка из Keitaro ----------

    def list_campaigns(self) -> list[CampaignSummary]:
        """Список кампаний из Keitaro со сводкой по нашим черновикам."""
        # синхронизируем названия кампаний с Keitaro
        kt_campaigns = self._keitaro.list_campaigns()
        summaries: list[CampaignSummary] = []
        for kt in kt_campaigns:
            campaign = self._upsert_campaign(kt.campaign_id, kt.name, kt.alias)
            fetched = campaign.fetched_at is not None
            streams = list(campaign.streams)
            summaries.append(CampaignSummary(
                id=campaign.id, keitaro_id=campaign.keitaro_id, name=campaign.name, alias=campaign.alias,
                fetched=fetched,
                streams_total=len(streams) if fetched else None,
                streams_with_offers=sum(1 for s in streams if s.offers) if fetched else None,
                dirty=any(draft_ops.is_dirty(stream_to_drafts(s)) for s in streams),
            ))
        self._session.commit()
        return summaries

    def get_campaign(self, campaign_id: int) -> CampaignView:
        """Кампания с потоками из нашей БД (без обращения к Keitaro)."""
        return self._campaign_view(self._get_campaign(campaign_id))

    def fetch_campaign(self, keitaro_campaign_id: int) -> CampaignView:
        """Загружает потоки кампании из Keitaro. Неопубликованные черновики не сбрасываются."""
        # сначала читаем Keitaro: при ошибке в нашей БД ничего не меняется
        kt_streams = self._keitaro.get_campaign_streams(keitaro_campaign_id)
        kt_campaign = next((c for c in self._keitaro.list_campaigns() if c.campaign_id == keitaro_campaign_id), None)
        name = kt_campaign.name if kt_campaign else f"Кампания {keitaro_campaign_id}"
        alias = kt_campaign.alias if kt_campaign else ""
        campaign = self._upsert_campaign(keitaro_campaign_id, name, alias)

        # обновляем потоки и офферы по данным Keitaro
        notes_by_stream: dict[int, list[str]] = {}
        seen_stream_ids: set[int] = set()
        for kt_stream in kt_streams:
            stream = self._upsert_stream(campaign, kt_stream)
            notes_by_stream[kt_stream.stream_id] = self._fetch_stream_offers(stream, kt_stream.offers)
            seen_stream_ids.add(kt_stream.stream_id)

        # потоки, которых в Keitaro больше нет, убираем у себя
        for stream in list(campaign.streams):
            if stream.keitaro_id not in seen_stream_ids:
                logger.info("Fetch: поток %s удалён в Keitaro, удаляем у себя", stream.keitaro_id)
                campaign.streams.remove(stream)

        campaign.fetched_at = datetime.now(timezone.utc)
        self._session.commit()
        logger.info("Fetch: кампания %s, потоков %s", keitaro_campaign_id, len(kt_streams))

        view = self._campaign_view(campaign)
        for stream_view in view.streams:
            stream_view.notes = notes_by_stream.get(stream_view.keitaro_id, [])
        return view

    # ---------- действия над черновиком ----------

    def add_offer(self, stream_id: int, offer_id: int) -> StreamView:
        """Добавляет оффер из базы Keitaro в черновик потока. Keitaro не меняется."""
        stream = self._get_stream(stream_id)

        # оффер должен существовать в базе Keitaro
        catalog_offer = self._keitaro.get_offer(offer_id)
        if catalog_offer is None:
            raise EntityNotFoundError("offer", offer_id)

        # меняем доменный список и только потом записи БД
        drafts = stream_to_drafts(stream)
        draft_ops.add_offer(drafts, offer_id, catalog_offer.name, catalog_offer.geo)
        return self._save(stream, drafts)

    def remove_offer(self, stream_id: int, offer_id: int) -> StreamView:
        """Убирает оффер из потока в черновике (неопубликованный удаляется полностью)."""
        stream = self._get_stream(stream_id)
        drafts = stream_to_drafts(stream)
        draft_ops.remove_offer(drafts, offer_id)
        return self._save(stream, drafts)

    def bring_back(self, stream_id: int, offer_id: int) -> StreamView:
        """Возвращает убранный оффер в черновик потока."""
        stream = self._get_stream(stream_id)
        drafts = stream_to_drafts(stream)
        draft_ops.bring_back(drafts, offer_id)
        return self._save(stream, drafts)

    def set_pin(self, stream_id: int, offer_id: int, pinned: bool) -> StreamView:
        """Закрепляет или открепляет вес оффера."""
        stream = self._get_stream(stream_id)
        drafts = stream_to_drafts(stream)
        draft_ops.set_pin(drafts, offer_id, pinned)
        return self._save(stream, drafts)

    def cancel(self, stream_id: int) -> StreamView:
        """Отменяет неопубликованные изменения потока."""
        stream = self._get_stream(stream_id)
        drafts = stream_to_drafts(stream)
        draft_ops.cancel(drafts)
        return self._save(stream, drafts)

    # ---------- предпросмотр и отправка ----------

    def preview(self, stream_id: int, resolutions: Optional[dict[str, str]] = None) -> PreviewView:
        """Показывает, что уйдёт в Keitaro: объединяет черновик с текущим потоком Keitaro, ничего не сохраняя."""
        stream = self._get_stream(stream_id)
        kt_stream = self._keitaro.get_stream(stream.keitaro_id)
        merged = merge_with_keitaro(stream_to_drafts(stream), kt_stream.offers, resolutions)

        # собираем представление результата без записи в БД
        view = self._stream_view_from_drafts(stream, merged.offers)
        can_push = not merged.unresolved and any(o.active for o in merged.offers)
        return PreviewView(
            stream=view,
            keitaro_offers=list(kt_stream.offers),
            changes=draft_ops.compute_changes(merged.offers),
            merge_items=merged.items,
            unresolved=merged.unresolved,
            can_push=can_push,
        )

    def push(self, stream_id: int, resolutions: Optional[dict[str, str]] = None) -> StreamView:
        """Отправляет поток в Keitaro: полностью заменяет его офферы итогом объединения."""
        stream = self._get_stream(stream_id)

        # объединяем черновик с текущим состоянием Keitaro
        kt_stream = self._keitaro.get_stream(stream.keitaro_id)
        merged = merge_with_keitaro(stream_to_drafts(stream), kt_stream.offers, resolutions)
        if merged.unresolved:
            raise MergeConflictError(merged.unresolved)
        draft_ops.ensure_pushable(merged.offers)

        # отправляем активные офферы; при ошибке Keitaro черновик в БД не менялся
        push_offers = [PushOffer(o.offer_id, o.weight) for o in merged.offers if o.active]
        self._keitaro.replace_stream_offers(stream.keitaro_id, push_offers)

        # успех: черновик становится опубликованным состоянием
        draft_ops.apply_push(merged.offers)
        logger.info("Push: поток %s отправлен, офферов %s", stream.keitaro_id, len(push_offers))
        try:
            return self._save(stream, merged.offers)
        except Exception:
            # Keitaro уже изменён, а запись в БД не удалась: следующая загрузка (Fetch) выровняет снимок
            logger.error("Push: поток %s записан в Keitaro, но сохранение в БД не удалось", stream.keitaro_id)
            raise

    # ---------- справочное ----------

    def search_offers(self, query: str) -> list[CatalogOffer]:
        """Поиск офферов в базе Keitaro по ID или названию."""
        return self._keitaro.search_offers(query)

    # ---------- внутренние помощники ----------

    def _get_campaign(self, campaign_id: int) -> Campaign:
        """Кампания по внутреннему ID или ошибка."""
        campaign = self._session.get(Campaign, campaign_id)
        if campaign is None:
            raise EntityNotFoundError("campaign", campaign_id)
        return campaign

    def _get_stream(self, stream_id: int) -> Stream:
        """Поток по внутреннему ID или ошибка."""
        stream = self._session.get(Stream, stream_id)
        if stream is None:
            raise EntityNotFoundError("stream", stream_id)
        return stream

    def _upsert_campaign(self, keitaro_id: int, name: str, alias: str) -> Campaign:
        """Создаёт или обновляет кампанию по ID из Keitaro."""
        campaign = self._session.scalar(select(Campaign).where(Campaign.keitaro_id == keitaro_id))
        if campaign is None:
            campaign = Campaign(keitaro_id=keitaro_id, name=name, alias=alias)
            self._session.add(campaign)
        else:
            campaign.name = name
            campaign.alias = alias
        self._session.flush()
        return campaign

    def _upsert_stream(self, campaign: Campaign, kt_stream: KtStream) -> Stream:
        """Создаёт или обновляет поток по ID из Keitaro."""
        stream = self._session.scalar(select(Stream).where(Stream.keitaro_id == kt_stream.stream_id))
        if stream is None:
            stream = Stream(keitaro_id=kt_stream.stream_id, name=kt_stream.name, position=kt_stream.position)
            campaign.streams.append(stream)
        else:
            stream.name = kt_stream.name
            stream.position = kt_stream.position
            if stream.campaign_id != campaign.id:
                stream.campaign = campaign
        self._session.flush()
        return stream

    def _fetch_stream_offers(self, stream: Stream, kt_offers: list[KtOfferState]) -> list[str]:
        """Обновляет офферы потока по данным Keitaro. Возвращает сообщения для пользователя.

        Если у потока есть неопубликованные изменения, они не сбрасываются: черновик объединяется с Keitaro,
        а спорные пункты разрешаются в пользу черновика (о них сообщается в возвращаемых сообщениях).
        """
        drafts = stream_to_drafts(stream)
        if not drafts and not kt_offers:
            return []  # поток без офферов: содержимое не храним

        # есть неопубликованные изменения: объединяем с Keitaro, черновик не сбрасываем
        if draft_ops.is_dirty(drafts):
            merged = merge_with_keitaro(drafts, kt_offers)
            for offer in merged.offers:
                if offer.temp_pinned:
                    # вес из Keitaro остаётся, но закреплённым не становится
                    offer.pinned = False
                    offer.temp_pinned = False
            new_drafts = merged.offers
            notes = [item.message for item in merged.items]
        else:
            new_drafts, notes = self._rebuild_from_keitaro(drafts, kt_offers)

        sync_stream_offers(stream, new_drafts)
        return notes

    @staticmethod
    def _rebuild_from_keitaro(drafts: list[DraftOffer], kt_offers: list[KtOfferState]) -> tuple[list[DraftOffer], list[str]]:
        """Поток без изменений: веса копируем из Keitaro, пропавшие офферы уходят в архив (Removed)."""
        old_by_id = {d.offer_id: d for d in drafts}
        kt_ids = {o.offer_id for o in kt_offers}
        notes: list[str] = []
        result: list[DraftOffer] = []

        # офферы из Keitaro в его порядке
        for kt in kt_offers:
            old = old_by_id.get(kt.offer_id)
            if old is None and drafts:
                notes.append(f"В потоке появился оффер {kt.offer_id}.")
            result.append(DraftOffer(
                offer_id=kt.offer_id, name=kt.name, geo=kt.geo, in_kt=True, kt_weight=kt.weight,
                active=True, weight=kt.weight, pinned=bool(old and old.pinned),
            ))

        # офферы, которых в Keitaro больше нет, переводим в архив
        for old in drafts:
            if old.offer_id in kt_ids:
                continue
            if old.in_kt:
                notes.append(f"Оффер {old.offer_id} удалён в Keitaro. Он оставлен в архиве как удалённый.")
            old.in_kt = False
            old.kt_weight = 0
            old.active = False
            old.pinned = False
            old.archived = True
            old.was_archived = True
            old.weight = 0
            result.append(old)

        # если в Keitaro доли не дают 100% (например, оффер удалили вручную), пересчитываем черновик до 100%
        total = sum(o.weight for o in result if o.active)
        if total != 100 and any(o.active for o in result):
            try:
                draft_ops.recalculate(result)
                notes.append(f"В Keitaro сумма долей {total}%. Пересчитали до 100%: отправьте поток, чтобы исправить Keitaro.")
            except WeightError:
                notes.append(
                    f"В Keitaro сумма долей {total}%, а закреплённые веса не позволяют пересчитать. "
                    "Открепите вес хотя бы одного оффера."
                )
        return result, notes

    def _save(self, stream: Stream, drafts: list[DraftOffer]) -> StreamView:
        """Записывает доменный список в БД и возвращает обновлённое представление потока."""
        sync_stream_offers(stream, drafts)
        self._session.commit()
        return self._stream_view(stream)

    def _stream_view(self, stream: Stream) -> StreamView:
        """Представление потока по данным БД."""
        return self._stream_view_from_drafts(stream, stream_to_drafts(stream))

    @staticmethod
    def _stream_view_from_drafts(stream: Stream, drafts: list[DraftOffer]) -> StreamView:
        """Представление потока по произвольному доменному списку (для предпросмотра)."""
        return StreamView(
            id=stream.id, keitaro_id=stream.keitaro_id, name=stream.name, position=stream.position,
            offers=[OfferView(offer=o, state=offer_state(o)) for o in drafts],
            dirty=draft_ops.is_dirty(drafts),
            weight_sum=active_sum(drafts),
        )

    def _campaign_view(self, campaign: Campaign) -> CampaignView:
        """Представление кампании со всеми потоками."""
        return CampaignView(
            id=campaign.id, keitaro_id=campaign.keitaro_id, name=campaign.name, alias=campaign.alias,
            fetched_at=campaign.fetched_at,
            streams=[self._stream_view(s) for s in campaign.streams],
        )
