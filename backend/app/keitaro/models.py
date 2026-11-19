"""Данные, которыми обмениваются сервисы и клиент Keitaro (без привязки к формату Admin API)."""
from dataclasses import dataclass, field
from typing import Optional

from app.domain.states import KtOfferState


@dataclass(frozen=True)
class KtCampaign:
    """Кампания Keitaro."""

    campaign_id: int  # ID кампании
    name: str  # название
    alias: str  # алиас (часть ссылки кампании)


@dataclass(frozen=True)
class KtReference:
    """Элемент справочника Keitaro: домен, группа или источник трафика."""

    ref_id: int  # ID записи
    name: str  # название (для домена — сам домен)


@dataclass(frozen=True)
class CatalogOffer:
    """Оффер из базы Keitaro (для поиска при добавлении в поток)."""

    offer_id: int  # ID оффера
    name: str  # название оффера
    geo: str = ""  # гео оффера через запятую (может быть пустым)


@dataclass
class KtStream:
    """Поток Keitaro. Адаптация полей Admin API к этой модели живёт в клиенте."""

    stream_id: int  # ID потока
    campaign_id: int  # ID кампании
    name: str  # название потока
    position: int  # позиция потока в кампании
    offers: list[KtOfferState] = field(default_factory=list)  # офферы потока; пусто — поток обёртка не показывает


@dataclass(frozen=True)
class PushOffer:
    """Оффер для полной замены офферов потока."""

    offer_id: int  # ID оффера
    share: int  # доля трафика, %


@dataclass(frozen=True)
class NewCampaign:
    """Параметры создания кампании. Домен, группа и источник необязательны."""

    name: str  # название кампании
    alias: str  # алиас кампании
    domain_id: Optional[int] = None  # ID домена
    group_id: Optional[int] = None  # ID группы
    source_id: Optional[int] = None  # ID источника трафика
