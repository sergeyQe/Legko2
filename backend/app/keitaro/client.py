"""Интерфейс клиента Keitaro. Сервисы зависят от него, а не от конкретной реализации (мок или HTTP)."""
from abc import ABC, abstractmethod
from typing import Optional

from app.keitaro.models import CatalogOffer, KtCampaign, KtReference, KtStream, NewCampaign, PushOffer


class KeitaroClient(ABC):
    """Контракт работы с Keitaro Admin API. Все методы могут бросать ошибки из app.keitaro.errors."""

    def close(self) -> None:
        """Освобождает ресурсы клиента (по умолчанию ничего не делает)."""

    @abstractmethod
    def list_campaigns(self) -> list[KtCampaign]:
        """Возвращает все кампании."""

    @abstractmethod
    def get_campaign(self, campaign_id: int) -> KtCampaign:
        """Возвращает одну кампанию (нужно для проверки названия перед действиями с ней)."""

    @abstractmethod
    def get_campaign_streams(self, campaign_id: int) -> list[KtStream]:
        """Возвращает все потоки кампании, включая потоки без офферов."""

    @abstractmethod
    def get_stream(self, stream_id: int) -> KtStream:
        """Возвращает текущее состояние одного потока."""

    @abstractmethod
    def replace_stream_offers(self, stream_id: int, offers: list[PushOffer]) -> KtStream:
        """Полностью заменяет офферы потока переданным списком и возвращает обновлённый поток."""

    @abstractmethod
    def search_offers(self, query: str) -> list[CatalogOffer]:
        """Ищет офферы в базе по ID или по части названия."""

    @abstractmethod
    def get_offer(self, offer_id: int) -> Optional[CatalogOffer]:
        """Возвращает оффер по точному ID или None, если его нет."""

    @abstractmethod
    def list_domains(self) -> list[KtReference]:
        """Возвращает домены."""

    @abstractmethod
    def list_groups(self) -> list[KtReference]:
        """Возвращает группы кампаний."""

    @abstractmethod
    def list_traffic_sources(self) -> list[KtReference]:
        """Возвращает источники трафика."""

    @abstractmethod
    def create_campaign(self, campaign: NewCampaign) -> KtCampaign:
        """Создаёт кампанию с ротацией потоков по весу."""

    @abstractmethod
    def create_country_redirect_stream(self, campaign_id: int, name: str, country_code: str, url: str) -> KtStream:
        """Создаёт поток: принимает посетителей из страны country_code и редиректит на url."""

    @abstractmethod
    def create_offer_stream(self, campaign_id: int, name: str, offer_id: int, share: int = 100) -> KtStream:
        """Создаёт поток без фильтров, который ведёт на один оффер."""
