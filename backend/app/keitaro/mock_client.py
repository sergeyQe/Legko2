"""Заглушка Keitaro с данными из скриншотов. Основной режим работы при отсутствии ключа Keitaro.

Умеет имитировать сбои и правки «со стороны» Keitaro для демонстрации и тестов (см. маршруты /mock/*).
"""
import copy
import logging
import threading
from dataclasses import dataclass
from typing import Optional

from app.domain.states import KtOfferState
from app.keitaro.client import KeitaroClient
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroEditionError,
    KeitaroError,
    KeitaroNotFoundError,
    KeitaroRejectedError,
    KeitaroUnreachableError,
)
from app.keitaro.models import CatalogOffer, KtCampaign, KtReference, KtStream, NewCampaign, PushOffer

logger = logging.getLogger(__name__)

FAILURE_KINDS = ("network", "auth", "edition", "not_found", "rejected")  # виды имитируемых сбоев
FAILURE_TARGETS = ("fetch", "push", "create_campaign", "create_stream1", "create_stream2")  # операции со сбоем

# каталог офферов (по скриншотам): ID, название, гео
_CATALOG = [
    CatalogOffer(11109, "Oxys [BEAUTY-CL-RO_0140]", "Румыния"),
    CatalogOffer(11110, "Oxys [BEAUTY-CL-CO_0141]", "Колумбия"),
    CatalogOffer(11111, "Oxys [BEAUTY-CL-CL_0142]", "Чили"),
    CatalogOffer(11112, "Oxys [BEAUTY-CL-BE_0155] [pl es -]", "Бельгия"),
    CatalogOffer(11113, "Dermia [SLIM-FR_0201]", "Франция"),
    CatalogOffer(11114, "Keto Drive [KETO-IT_0087]", "Италия"),
    CatalogOffer(11115, "Gelo Pro [JOINT-PL_0310]", "Польша"),
    CatalogOffer(11120, "Vitalis [HEART-DE_0042]", "Германия"),
]
_DOMAINS = [KtReference(1, "in.posdk.xyz"), KtReference(2, "go.demo-track.net"), KtReference(3, "click.example-kt.com")]
_GROUPS = [KtReference(1, "FORTESTS"), KtReference(2, "Основные"), KtReference(3, "Новые гео")]
_SOURCES = [KtReference(1, "FORTESTS"), KtReference(2, "Facebook"), KtReference(3, "Google Ads")]


@dataclass
class _Failure:
    """Запланированный сбой: сколько раз ещё сработает для операции."""

    kind: str  # вид сбоя из FAILURE_KINDS
    target: str  # операция из FAILURE_TARGETS
    times: int  # сколько вызовов подряд завершатся ошибкой


class MockKeitaroClient(KeitaroClient):
    """Хранит кампании, потоки и офферы в памяти процесса."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.reset()

    # ---------- служебное для демонстрации и тестов ----------

    def reset(self) -> None:
        """Возвращает данные к исходным (по скриншотам) и снимает все запланированные сбои."""
        with self._lock:
            self._campaigns: dict[int, KtCampaign] = {
                93212: KtCampaign(93212, "campaign 2", "campaign-2"),
                93215: KtCampaign(93215, "campaign 5", "campaign-5"),
            }
            self._streams: dict[int, KtStream] = {
                1: KtStream(1, 93212, "Поток 1", 1, []),  # поток-редирект без офферов
                2: KtStream(2, 93212, "Поток 2", 2, [
                    KtOfferState(11109, "Oxys [BEAUTY-CL-RO_0140]", "Румыния", 33),
                    KtOfferState(11110, "Oxys [BEAUTY-CL-CO_0141]", "Колумбия", 33),
                    KtOfferState(11111, "Oxys [BEAUTY-CL-CL_0142]", "Чили", 34),
                ]),
                3: KtStream(3, 93215, "Поток 1", 1, [
                    KtOfferState(11113, "Dermia [SLIM-FR_0201]", "Франция", 50),
                    KtOfferState(11114, "Keto Drive [KETO-IT_0087]", "Италия", 50),
                ]),
            }
            self._failures: list[_Failure] = []
            self._next_campaign_id = 93300
            self._next_stream_id = 100
            logger.info("[mock] данные Keitaro сброшены")

    def fail_next(self, kind: str, target: str, times: int = 1) -> None:
        """Планирует сбой: следующие times вызовов операции target завершатся ошибкой вида kind."""
        if kind not in FAILURE_KINDS:
            raise ValueError(f"Неизвестный вид сбоя: {kind}")
        if target not in FAILURE_TARGETS:
            raise ValueError(f"Неизвестная операция: {target}")
        if times < 1:
            raise ValueError("Число вызовов должно быть не меньше 1")
        with self._lock:
            self._failures.append(_Failure(kind, target, times))
        logger.info("[mock] запланирован сбой %s на операции %s, раз: %s", kind, target, times)

    def external_offer_added(self, stream_id: int, offer_id: int, weight: int) -> None:
        """Имитирует: в Keitaro вручную добавили оффер в поток."""
        with self._lock:
            stream = self._get_stream(stream_id)
            catalog = self._catalog_offer(offer_id)
            if any(o.offer_id == offer_id for o in stream.offers):
                raise KeitaroRejectedError(f"Offer {offer_id} is already in the stream")
            stream.offers.append(KtOfferState(offer_id, catalog.name, catalog.geo, weight))
        logger.info("[mock] правка в Keitaro: в поток %s добавлен оффер %s (%s%%)", stream_id, offer_id, weight)

    def external_weight_changed(self, stream_id: int, offer_id: int, weight: int) -> None:
        """Имитирует: в Keitaro вручную изменили вес оффера в потоке."""
        with self._lock:
            stream = self._get_stream(stream_id)
            for index, offer in enumerate(stream.offers):
                if offer.offer_id == offer_id:
                    stream.offers[index] = KtOfferState(offer.offer_id, offer.name, offer.geo, weight)
                    break
            else:
                raise KeitaroNotFoundError(f"Offer {offer_id} not in stream", entity="offer", entity_id=offer_id)
        logger.info("[mock] правка в Keitaro: у оффера %s в потоке %s вес %s%%", offer_id, stream_id, weight)

    def external_offer_removed(self, stream_id: int, offer_id: int) -> None:
        """Имитирует: в Keitaro вручную удалили оффер из потока."""
        with self._lock:
            stream = self._get_stream(stream_id)
            before = len(stream.offers)
            stream.offers = [o for o in stream.offers if o.offer_id != offer_id]
            if len(stream.offers) == before:
                raise KeitaroNotFoundError(f"Offer {offer_id} not in stream", entity="offer", entity_id=offer_id)
        logger.info("[mock] правка в Keitaro: из потока %s удалён оффер %s", stream_id, offer_id)

    def describe(self) -> dict:
        """Текущее состояние заглушки для отладки (потоки, офферы, запланированные сбои)."""
        with self._lock:
            return {
                "campaigns": [vars(c).copy() for c in self._campaigns.values()],
                "streams": [
                    {"id": s.stream_id, "campaign_id": s.campaign_id, "name": s.name,
                     "offers": [{"offer_id": o.offer_id, "weight": o.weight} for o in s.offers]}
                    for s in self._streams.values()
                ],
                "failures": [vars(f).copy() for f in self._failures],
            }

    # ---------- внутренние помощники ----------

    def _maybe_fail(self, target: str) -> None:
        """Бросает запланированную ошибку, если для операции есть сбой."""
        for failure in self._failures:
            if failure.target == target and failure.times > 0:
                failure.times -= 1
                self._failures = [f for f in self._failures if f.times > 0]
                logger.info("[mock] сбой %s на операции %s", failure.kind, target)
                raise self._build_error(failure.kind)

    @staticmethod
    def _build_error(kind: str) -> KeitaroError:
        """Создаёт ошибку заданного вида с текстами, похожими на ответы Keitaro."""
        if kind == "network":
            return KeitaroUnreachableError("Таймаут запроса к Keitaro")
        if kind == "auth":
            return KeitaroAuthError("Access denied", status_code=401)
        if kind == "edition":
            return KeitaroEditionError("Admin API is not available in that edition", status_code=402)
        if kind == "not_found":
            return KeitaroNotFoundError("Entity not found", entity="stream")
        return KeitaroRejectedError("Bad request: invalid data", status_code=400)

    def _get_stream(self, stream_id: int) -> KtStream:
        """Возвращает поток из хранилища или бросает NotFound."""
        stream = self._streams.get(stream_id)
        if stream is None:
            raise KeitaroNotFoundError(f"Stream {stream_id} not found", entity="stream", entity_id=stream_id)
        return stream

    def _catalog_offer(self, offer_id: int) -> CatalogOffer:
        """Возвращает оффер из каталога или бросает NotFound."""
        offer = next((o for o in _CATALOG if o.offer_id == offer_id), None)
        if offer is None:
            raise KeitaroNotFoundError(f"Offer {offer_id} not found", entity="offer", entity_id=offer_id)
        return offer

    @staticmethod
    def _copy(stream: KtStream) -> KtStream:
        """Копия потока, чтобы вызывающий код не менял хранилище."""
        return copy.deepcopy(stream)

    # ---------- контракт клиента ----------

    def list_campaigns(self) -> list[KtCampaign]:
        with self._lock:
            return list(self._campaigns.values())

    def get_campaign_streams(self, campaign_id: int) -> list[KtStream]:
        with self._lock:
            self._maybe_fail("fetch")
            if campaign_id not in self._campaigns:
                raise KeitaroNotFoundError(f"Campaign {campaign_id} not found", entity="campaign", entity_id=campaign_id)
            streams = [s for s in self._streams.values() if s.campaign_id == campaign_id]
            return [self._copy(s) for s in sorted(streams, key=lambda s: s.position)]

    def get_stream(self, stream_id: int) -> KtStream:
        with self._lock:
            self._maybe_fail("fetch")
            return self._copy(self._get_stream(stream_id))

    def replace_stream_offers(self, stream_id: int, offers: list[PushOffer]) -> KtStream:
        with self._lock:
            self._maybe_fail("push")
            stream = self._get_stream(stream_id)
            # правила Keitaro, которые мы предполагаем: офферы существуют, доли дают 100
            if not offers:
                raise KeitaroRejectedError("Stream must contain at least one offer", status_code=400)
            if sum(o.share for o in offers) != 100:
                raise KeitaroRejectedError("Offer shares must sum to 100", status_code=400)
            new_offers = []
            for push in offers:
                catalog = self._catalog_offer(push.offer_id)
                new_offers.append(KtOfferState(push.offer_id, catalog.name, catalog.geo, push.share))
            stream.offers = new_offers
            logger.info("[mock] поток %s: офферы заменены (%s шт.)", stream_id, len(new_offers))
            return self._copy(stream)

    def search_offers(self, query: str) -> list[CatalogOffer]:
        needle = query.strip().casefold()
        if not needle:
            return []
        with self._lock:
            found = [o for o in _CATALOG if str(o.offer_id) == needle or needle in o.name.casefold()]
        return found[:20]

    def get_offer(self, offer_id: int) -> Optional[CatalogOffer]:
        return next((o for o in _CATALOG if o.offer_id == offer_id), None)

    def list_domains(self) -> list[KtReference]:
        return list(_DOMAINS)

    def list_groups(self) -> list[KtReference]:
        return list(_GROUPS)

    def list_traffic_sources(self) -> list[KtReference]:
        return list(_SOURCES)

    def create_campaign(self, campaign: NewCampaign) -> KtCampaign:
        with self._lock:
            self._maybe_fail("create_campaign")
            # проверяем уникальность алиаса и существование справочных записей
            if any(c.alias == campaign.alias for c in self._campaigns.values()):
                raise KeitaroRejectedError("Alias already exists", status_code=400)
            for ref_id, items, label in (
                (campaign.domain_id, _DOMAINS, "Domain"),
                (campaign.group_id, _GROUPS, "Group"),
                (campaign.source_id, _SOURCES, "Traffic source"),
            ):
                if ref_id is not None and not any(r.ref_id == ref_id for r in items):
                    raise KeitaroRejectedError(f"{label} {ref_id} not found", status_code=400)
            self._next_campaign_id += 1
            created = KtCampaign(self._next_campaign_id, campaign.name, campaign.alias)
            self._campaigns[created.campaign_id] = created
            logger.info("[mock] создана кампания %s (%s)", created.campaign_id, created.alias)
            return created

    def create_country_redirect_stream(self, campaign_id: int, name: str, country_code: str, url: str) -> KtStream:
        with self._lock:
            self._maybe_fail("create_stream1")
            if campaign_id not in self._campaigns:
                raise KeitaroNotFoundError(f"Campaign {campaign_id} not found", entity="campaign", entity_id=campaign_id)
            return self._create_stream(campaign_id, name, [])

    def create_offer_stream(self, campaign_id: int, name: str, offer_id: int, share: int = 100) -> KtStream:
        with self._lock:
            self._maybe_fail("create_stream2")
            if campaign_id not in self._campaigns:
                raise KeitaroNotFoundError(f"Campaign {campaign_id} not found", entity="campaign", entity_id=campaign_id)
            catalog = next((o for o in _CATALOG if o.offer_id == offer_id), None)
            if catalog is None:
                raise KeitaroRejectedError(f"Offer {offer_id} not found", status_code=400)
            return self._create_stream(campaign_id, name, [KtOfferState(offer_id, catalog.name, catalog.geo, share)])

    def _create_stream(self, campaign_id: int, name: str, offers: list[KtOfferState]) -> KtStream:
        """Создаёт поток в конце списка потоков кампании."""
        self._next_stream_id += 1
        position = 1 + max((s.position for s in self._streams.values() if s.campaign_id == campaign_id), default=0)
        stream = KtStream(self._next_stream_id, campaign_id, name, position, offers)
        self._streams[stream.stream_id] = stream
        logger.info("[mock] создан поток %s в кампании %s", stream.stream_id, campaign_id)
        return self._copy(stream)
