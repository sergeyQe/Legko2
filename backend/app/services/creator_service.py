"""Сервис создателя кампаний: кампания с двумя потоками (страна → Google, остальные → оффер)."""
import logging
from typing import Optional

from app.domain.errors import ValidationError
from app.domain.naming import make_alias, normalize_geo, normalize_name
from app.keitaro.client import KeitaroClient
from app.keitaro.errors import KeitaroError
from app.keitaro.models import NewCampaign
from app.services.errors import CreatePartialError
from app.services.views import CreateReport, StepResult

logger = logging.getLogger(__name__)

REDIRECT_URL = "https://google.com"  # куда уходят посетители из выбранной страны
STREAM1_NAME = "Поток 1"
STREAM2_NAME = "Поток 2"


class CreatorService:
    """Создаёт кампанию в Keitaro по шагам и сообщает, что получилось."""

    def __init__(self, keitaro: KeitaroClient, campaign_prefix: str) -> None:
        # стенд Keitaro общий: новые кампании всегда получают префикс, чужие кампании не трогаем
        if not campaign_prefix:
            raise ValueError("CAMPAIGN_PREFIX не задан: без префикса сервис не может отличить свои кампании от чужих")
        self._keitaro = keitaro
        self._prefix = campaign_prefix

    def full_name(self, name: str) -> str:
        """Название кампании с префиксом (если пользователь уже написал префикс, второй раз не добавляется)."""
        clean = normalize_name(name)
        return clean if clean.casefold().startswith(self._prefix.casefold()) else self._prefix + clean

    def create_campaign(
        self,
        name: str,
        geo: str,
        offer_id: int,
        domain_id: Optional[int] = None,
        group_id: Optional[int] = None,
        source_id: Optional[int] = None,
    ) -> CreateReport:
        """Создаёт кампанию и два потока. Домен, группа и источник необязательны.

        Ошибка на шаге создания кампании пробрасывается как есть (ничего не создано).
        Ошибка после неё приводит к CreatePartialError с отчётом; созданное не удаляется.
        """
        # проверяем ввод до обращений к Keitaro; к названию добавляется префикс стенда
        clean_name = normalize_name(self.full_name(name))
        country = normalize_geo(geo)
        alias = make_alias(clean_name)
        offer = self._keitaro.get_offer(offer_id)
        if offer is None:
            raise ValidationError("offer", f"Оффер {offer_id} не найден в Keitaro.")

        steps = [
            StepResult("campaign", f"Кампания «{clean_name}» (алиас {alias})", "skipped"),
            StepResult("stream1", f"{STREAM1_NAME}: страна {country} принимается, редирект на {REDIRECT_URL}", "skipped"),
            StepResult("stream2", f"{STREAM2_NAME}: оффер {offer_id}, доля 100%", "skipped"),
        ]

        # шаг 1: кампания; при ошибке ничего не создано, поэтому отдаём исходную ошибку
        campaign = self._keitaro.create_campaign(
            NewCampaign(name=clean_name, alias=alias, domain_id=domain_id, group_id=group_id, source_id=source_id)
        )
        steps[0].status = "ok"
        logger.info("Создание кампании: кампания %s создана (%s)", campaign.campaign_id, alias)
        report = CreateReport(ok=False, campaign_id=campaign.campaign_id, name=clean_name, alias=alias, steps=steps)

        # шаги 2 и 3: потоки; при ошибке кампания остаётся в Keitaro, возвращаем отчёт
        self._run_step(report, 1, lambda: self._keitaro.create_country_redirect_stream(
            campaign.campaign_id, STREAM1_NAME, country, REDIRECT_URL))
        self._run_step(report, 2, lambda: self._keitaro.create_offer_stream(
            campaign.campaign_id, STREAM2_NAME, offer_id, 100))

        report.ok = True
        logger.info("Создание кампании: кампания %s готова", campaign.campaign_id)
        return report

    def retry_stream2(
        self, campaign_id: int, offer_id: int, name: str = "", alias: str = "", geo: str = ""
    ) -> CreateReport:
        """Повторяет создание потока 2 для кампании, у которой он не создался.

        name, alias и geo необязательны и нужны только для подробных подписей шагов в отчёте.
        """
        # повтор разрешён только для наших кампаний (по префиксу названия)
        campaign = self._keitaro.get_campaign(campaign_id)
        if not campaign.name.casefold().startswith(self._prefix.casefold()):
            raise ValidationError("campaign", "Эта кампания создана не нашим сервисом: действия над ней запрещены.")

        # если поток с этим оффером уже есть, повторно не создаём
        streams = self._keitaro.get_campaign_streams(campaign_id)
        if not any(not s.offers for s in streams):
            raise ValidationError("campaign", "В кампании нет потока 1 (без офферов): повторить создание потока 2 нельзя.")
        already = any(o.offer_id == offer_id for s in streams for o in s.offers)

        # подписи такие же подробные, как при первом создании, если известны название, алиас и страна
        campaign_text = f"Кампания «{name}» (алиас {alias})" if name and alias else "Кампания создана"
        country = geo.strip().upper()
        stream1_text = (
            f"{STREAM1_NAME}: страна {country} принимается, редирект на {REDIRECT_URL}" if country else f"{STREAM1_NAME} создан"
        )
        steps = [
            StepResult("campaign", campaign_text, "ok"),
            StepResult("stream1", stream1_text, "ok"),
            StepResult("stream2", f"{STREAM2_NAME}: оффер {offer_id}, доля 100%", "skipped"),
        ]
        report = CreateReport(ok=False, campaign_id=campaign_id, name=name, alias=alias, steps=steps)
        if already:
            steps[2].status = "ok"
            report.ok = True
            logger.info("Повтор потока 2: у кампании %s он уже есть", campaign_id)
            return report

        # создаём поток 2 ещё раз
        self._run_step(report, 2, lambda: self._keitaro.create_offer_stream(campaign_id, STREAM2_NAME, offer_id, 100))
        report.ok = True
        logger.info("Повтор потока 2: создан для кампании %s", campaign_id)
        return report

    @staticmethod
    def _run_step(report: CreateReport, index: int, action) -> None:
        """Выполняет шаг; при ошибке Keitaro отмечает шаг и бросает CreatePartialError с отчётом."""
        step = report.steps[index]
        try:
            action()
        except KeitaroError as exc:
            step.status = "failed"
            step.error = exc.message or exc.__class__.__name__
            logger.warning("Создание кампании: шаг %s не выполнен: %s", step.name, step.error)
            raise CreatePartialError(report) from exc
        step.status = "ok"
