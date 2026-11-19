"""Сервис справочников: домены, группы, источники и значения по умолчанию для новой кампании."""
import logging
from typing import Optional

from app.config import Settings
from app.keitaro.client import KeitaroClient
from app.keitaro.models import CatalogOffer, KtReference
from app.services.views import ReferenceDefaults

logger = logging.getLogger(__name__)


class ReferenceService:
    """Справочники Keitaro для формы создания кампании и поиска офферов."""

    def __init__(self, keitaro: KeitaroClient, settings: Settings) -> None:
        self._keitaro = keitaro
        self._settings = settings

    def domains(self) -> list[KtReference]:
        """Домены из Keitaro."""
        return self._keitaro.list_domains()

    def groups(self) -> list[KtReference]:
        """Группы кампаний из Keitaro."""
        return self._keitaro.list_groups()

    def sources(self) -> list[KtReference]:
        """Источники трафика из Keitaro."""
        return self._keitaro.list_traffic_sources()

    def search_offers(self, query: str) -> list[CatalogOffer]:
        """Поиск офферов по ID или названию."""
        return self._keitaro.search_offers(query)

    def defaults(self) -> ReferenceDefaults:
        """Находит ID значений по умолчанию по их названиям из настроек (регистр не важен)."""
        domain = self._find(self.domains(), self._settings.default_domain)
        group = self._find(self.groups(), self._settings.default_group)
        source = self._find(self.sources(), self._settings.default_source)

        # значения, которых нет в Keitaro, остаются пустыми и попадают в список missing
        missing = [
            name for name, found in (
                (self._settings.default_domain, domain),
                (self._settings.default_group, group),
                (self._settings.default_source, source),
            ) if name and found is None
        ]
        if missing:
            logger.warning("Значения по умолчанию не найдены в Keitaro: %s", missing)
        return ReferenceDefaults(
            domain_id=domain.ref_id if domain else None,
            group_id=group.ref_id if group else None,
            source_id=source.ref_id if source else None,
            missing=missing,
        )

    @staticmethod
    def _find(items: list[KtReference], name: str) -> Optional[KtReference]:
        """Запись справочника по названию без учёта регистра."""
        needle = (name or "").strip().casefold()
        return next((i for i in items if i.name.strip().casefold() == needle), None) if needle else None
