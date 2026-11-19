"""Операции над черновиком потока: добавить, убрать, вернуть, закрепить, отменить, отправить.

Все функции работают со списком DraftOffer на месте и ничего не знают о БД и сети.
При ошибке список возвращается в исходное состояние (внимание: объекты в нём заменяются копиями).
"""
import copy
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal, Optional

from app.domain.errors import (
    EmptyStreamError,
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    OfferRemovedError,
    OfferStateError,
)
from app.domain.states import DraftOffer, OfferState, offer_state
from app.domain.weights import calculate_weights

logger = logging.getLogger(__name__)

ChangeKind = Literal["add", "remove", "change"]


@dataclass
class Change:
    """Одно отличие черновика от опубликованного состояния (для предпросмотра)."""

    kind: ChangeKind  # add — добавится, remove — уйдёт в архив, change — изменится вес
    offer: DraftOffer  # оффер, к которому относится изменение
    from_weight: Optional[int]  # вес в Keitaro сейчас (None, если оффера там нет)
    to_weight: int  # вес после отправки
    note: str  # короткое пояснение для пользователя


@contextmanager
def _rollback_on_error(offers: list[DraftOffer]) -> Iterator[None]:
    """Откатывает список офферов к исходному состоянию, если внутри блока возникла ошибка."""
    backup = copy.deepcopy(offers)
    try:
        yield
    except Exception:
        offers[:] = backup
        raise


def _find(offers: list[DraftOffer], offer_id: int) -> Optional[DraftOffer]:
    """Ищет оффер потока по ID."""
    return next((o for o in offers if o.offer_id == offer_id), None)


def _get(offers: list[DraftOffer], offer_id: int) -> DraftOffer:
    """Возвращает оффер потока или бросает OfferNotFoundError."""
    offer = _find(offers, offer_id)
    if offer is None:
        raise OfferNotFoundError(offer_id)
    return offer


def recalculate(offers: list[DraftOffer]) -> None:
    """Пересчитывает веса: закреплённые и временно зафиксированные не меняются, остаток делится поровну."""
    active = [o for o in offers if o.active]
    weights = calculate_weights([o.weight if o.pinned else None for o in active])
    for offer, weight in zip(active, weights):
        offer.weight = weight
    # неактивные офферы всегда имеют вес 0
    for offer in offers:
        if not offer.active:
            offer.weight = 0


def add_offer(offers: list[DraftOffer], offer_id: int, name: str, geo: str = "") -> DraftOffer:
    """Добавляет оффер в черновик и пересчитывает веса. Возвращает добавленный оффер."""
    # оффер не должен уже быть в потоке (активным или в удалённом состоянии)
    existing = _find(offers, offer_id)
    if existing is not None:
        if existing.active:
            raise OfferAlreadyInStreamError(offer_id)
        raise OfferRemovedError(offer_id)

    with _rollback_on_error(offers):
        # новый оффер: в Keitaro его ещё нет
        offer = DraftOffer(offer_id=offer_id, name=name, geo=geo, in_kt=False, active=True)
        offers.append(offer)
        recalculate(offers)
    logger.info("Черновик: добавлен оффер %s", offer_id)
    return _get(offers, offer_id)


def remove_offer(offers: list[DraftOffer], offer_id: int) -> bool:
    """Убирает оффер из потока. Возвращает True, если оффер удалён полностью (его не было в Keitaro)."""
    offer = _get(offers, offer_id)
    if not offer.active:
        raise OfferStateError(f"Оффер {offer_id} уже убран из потока.")

    with _rollback_on_error(offers):
        if not offer.in_kt:
            # неопубликованный оффер удаляется целиком, в архив он не попадает
            offers.remove(offer)
            deleted = True
        else:
            # опубликованный оффер получает вес 0 и уйдёт в архив после отправки
            offer.active = False
            offer.pinned = False
            deleted = False
        recalculate(offers)
    logger.info("Черновик: убран оффер %s (удалён полностью: %s)", offer_id, deleted)
    return deleted


def bring_back(offers: list[DraftOffer], offer_id: int) -> DraftOffer:
    """Возвращает убранный оффер в поток и пересчитывает веса."""
    offer = _get(offers, offer_id)
    if offer.active:
        raise OfferStateError(f"Оффер {offer_id} уже находится в потоке.")

    with _rollback_on_error(offers):
        # оффер из архива возвращается как неопубликованный, убираемый — как прежний опубликованный
        offer.was_archived = offer.archived
        offer.archived = False
        offer.active = True
        offer.pinned = False
        offer.weight = 0
        recalculate(offers)
    logger.info("Черновик: возвращён оффер %s", offer_id)
    return _get(offers, offer_id)


def set_pin(offers: list[DraftOffer], offer_id: int, pinned: bool) -> DraftOffer:
    """Закрепляет или открепляет вес оффера. При невозможном распределении состояние не меняется."""
    offer = _get(offers, offer_id)
    if not offer.active:
        raise OfferStateError("Нельзя закрепить вес убранного оффера.")

    with _rollback_on_error(offers):
        offer.pinned = pinned
        offer.temp_pinned = False
        recalculate(offers)
    logger.info("Черновик: оффер %s, вес %s", offer_id, "закреплён" if pinned else "откреплён")
    return _get(offers, offer_id)


def cancel(offers: list[DraftOffer]) -> None:
    """Отменяет все неопубликованные изменения: поток снова совпадает с Keitaro."""
    # добавленные в черновике офферы удаляются, архивные остаются в архиве
    offers[:] = [o for o in offers if o.in_kt or o.was_archived]
    for offer in offers:
        if offer.in_kt:
            offer.active = True
            offer.weight = offer.kt_weight
        else:
            offer.active = False
            offer.archived = True
            offer.weight = 0
        offer.pinned = False
        offer.temp_pinned = False
    logger.info("Черновик отменён")


def ensure_pushable(offers: list[DraftOffer]) -> None:
    """Проверяет, что поток можно отправить: в нём есть хотя бы один активный оффер."""
    if not any(o.active for o in offers):
        raise EmptyStreamError()


def apply_push(offers: list[DraftOffer]) -> None:
    """Применяет успешную отправку: черновик становится опубликованным состоянием."""
    ensure_pushable(offers)
    for offer in offers:
        if offer.active:
            # активный оффер теперь есть в Keitaro с текущим весом
            offer.in_kt = True
            offer.kt_weight = offer.weight
            offer.archived = False
            offer.was_archived = False
            if offer.temp_pinned:
                offer.pinned = False
                offer.temp_pinned = False
        elif offer.in_kt:
            # убранный оффер исчез из Keitaro и остался в архиве обёртки
            offer.in_kt = False
            offer.kt_weight = 0
            offer.archived = True
            offer.was_archived = True
    logger.info("Черновик применён: активных офферов %s", sum(1 for o in offers if o.active))


def compute_changes(offers: list[DraftOffer]) -> list[Change]:
    """Список отличий черновика от Keitaro для предпросмотра и признака «не опубликован»."""
    changes: list[Change] = []
    for offer in offers:
        state = offer_state(offer)
        if state == OfferState.ADDED:
            note = "вернётся из архива" if offer.was_archived else "новый оффер в потоке"
            changes.append(Change("add", offer, None, offer.weight, note))
        elif state == OfferState.REMOVING:
            changes.append(Change("remove", offer, offer.kt_weight, 0, "уйдёт в архив"))
        elif state == OfferState.PUBLISHED and offer.weight != offer.kt_weight:
            note = "вес закреплён" if offer.pinned else "пересчёт долей"
            changes.append(Change("change", offer, offer.kt_weight, offer.weight, note))
    return changes


def is_dirty(offers: list[DraftOffer]) -> bool:
    """Есть ли у потока неопубликованные изменения (поток «жёлтый»)."""
    return bool(compute_changes(offers))
