"""Модель оффера в черновике потока и его состояния."""
from dataclasses import dataclass
from enum import Enum


class OfferState(str, Enum):
    """Состояние оффера в потоке с точки зрения публикации в Keitaro."""

    PUBLISHED = "published"  # есть в Keitaro и активен
    ADDED = "added"  # добавлен в черновике, в Keitaro ещё нет
    REMOVING = "removing"  # убран в черновике, в Keitaro ещё есть (уйдёт при отправке)
    REMOVED = "removed"  # в архиве обёртки: в Keitaro нет, в черновике не активен


@dataclass
class DraftOffer:
    """Оффер потока: его опубликованное состояние (снимок Keitaro) и состояние черновика."""

    offer_id: int  # ID оффера в Keitaro
    name: str  # название оффера
    geo: str = ""  # гео оффера (для подписи)
    in_kt: bool = False  # есть в Keitaro по последней загрузке или отправке
    kt_weight: int = 0  # вес в Keitaro по последней загрузке (снимок для merge и «Было»)
    active: bool = True  # активен ли в черновике
    weight: int = 0  # вес в черновике, %
    pinned: bool = False  # вес закреплён пользователем
    archived: bool = False  # лежит в архиве обёртки (удалён после отправки)
    was_archived: bool = False  # был в архиве до возвращения в черновик (нужно для CANCEL)
    temp_pinned: bool = False  # вес временно зафиксирован при merge (вес из Keitaro), снимается после отправки


@dataclass(frozen=True)
class KtOfferState:
    """Оффер потока в Keitaro на момент запроса (для сравнения при merge)."""

    offer_id: int  # ID оффера
    name: str  # название оффера
    geo: str  # гео оффера
    weight: int  # вес в потоке, %


def offer_state(offer: DraftOffer) -> OfferState:
    """Определяет состояние оффера по флагам in_kt и active."""
    if offer.active:
        return OfferState.PUBLISHED if offer.in_kt else OfferState.ADDED
    return OfferState.REMOVING if offer.in_kt else OfferState.REMOVED


def active_sum(offers: list[DraftOffer]) -> int:
    """Сумма весов активных офферов потока."""
    return sum(o.weight for o in offers if o.active)
