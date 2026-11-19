"""Трёхсторонний merge: снимок Keitaro при загрузке, черновик пользователя, текущий поток в Keitaro."""
import copy
import logging
from dataclasses import dataclass
from typing import Literal, Optional

from app.domain.draft import recalculate
from app.domain.errors import InvalidResolutionError, WeightError
from app.domain.states import DraftOffer, KtOfferState

logger = logging.getLogger(__name__)

MergeKind = Literal["auto", "conflict"]
RESOLUTIONS = ("draft", "keitaro")


@dataclass
class MergeItem:
    """Один пункт объединения: решено автоматически или требует выбора пользователя."""

    key: str  # уникальный ключ пункта (по нему приходит решение пользователя)
    kind: MergeKind  # auto — объединено само, conflict — нужно решение
    offer_id: int  # оффер, к которому относится пункт
    message: str  # описание для пользователя
    resolution: Optional[str] = None  # выбранное решение для конфликта: draft или keitaro


@dataclass
class MergeResult:
    """Итог объединения: офферы после merge и список пунктов."""

    offers: list[DraftOffer]  # офферы потока после объединения (веса пересчитаны)
    items: list[MergeItem]  # что произошло при объединении

    @property
    def needs_merge(self) -> bool:
        """Были ли расхождения с Keitaro."""
        return bool(self.items)

    @property
    def unresolved(self) -> list[MergeItem]:
        """Конфликты, по которым пользователь ещё не принял решение."""
        return [i for i in self.items if i.kind == "conflict" and i.resolution is None]


def _auto(key: str, offer_id: int, message: str) -> MergeItem:
    """Пункт, объединённый автоматически."""
    return MergeItem(key=key, kind="auto", offer_id=offer_id, message=message)


def _conflict(key: str, offer_id: int, message: str, resolutions: dict[str, str]) -> MergeItem:
    """Пункт-конфликт с решением пользователя, если оно уже есть."""
    return MergeItem(key=key, kind="conflict", offer_id=offer_id, message=message, resolution=resolutions.get(key))


def _archive(offer: DraftOffer) -> None:
    """Переводит оффер в архив обёртки (его нет в Keitaro и он не активен)."""
    offer.in_kt = False
    offer.kt_weight = 0
    offer.active = False
    offer.pinned = False
    offer.temp_pinned = False
    offer.archived = True
    offer.was_archived = True
    offer.weight = 0


def _fix_weight(offer: DraftOffer, weight: int) -> None:
    """Временно фиксирует вес оффера (вес из Keitaro) на время пересчёта."""
    offer.pinned = True
    offer.temp_pinned = True
    offer.weight = weight


def _validate_resolutions(resolutions: dict[str, str]) -> None:
    """Проверяет, что решения принадлежат допустимому набору."""
    for key, value in resolutions.items():
        if value not in RESOLUTIONS:
            raise InvalidResolutionError(f"Неверное решение «{value}» для пункта {key}.")


def merge_with_keitaro(
    draft_offers: list[DraftOffer],
    keitaro_offers: list[KtOfferState],
    resolutions: Optional[dict[str, str]] = None,
) -> MergeResult:
    """Объединяет черновик с текущим состоянием потока в Keitaro.

    База сравнения — поля in_kt и kt_weight у офферов черновика (снимок последней загрузки).
    Конфликты без решения не блокируют расчёт: для них временно применяется вариант «draft».
    Блокировать отправку по MergeResult.unresolved должен вызывающий код.
    Решения с неизвестными ключами игнорируются (например, устаревшие); неверное значение решения — ошибка.
    """
    resolutions = dict(resolutions or {})
    _validate_resolutions(resolutions)

    offers = copy.deepcopy(draft_offers)
    original_count = len(offers)
    theirs = {o.offer_id: o for o in keitaro_offers}
    known = {o.offer_id for o in offers}
    items: list[MergeItem] = []

    # офферы, которые появились в Keitaro после загрузки, сохраняем в потоке
    for kt in keitaro_offers:
        if kt.offer_id not in known:
            offers.append(
                DraftOffer(
                    offer_id=kt.offer_id, name=kt.name, geo=kt.geo,
                    in_kt=True, kt_weight=kt.weight, active=True, weight=kt.weight,
                )
            )
            items.append(_auto(
                f"{kt.offer_id}:added_in_kt", kt.offer_id,
                f"Оффер {kt.offer_id} добавлен в Keitaro после загрузки. Сохраняем его в потоке, доли пересчитаем.",
            ))

    # остальные офферы сравниваем с тем, что сейчас в Keitaro
    for offer in offers[:original_count]:
        kt = theirs.get(offer.offer_id)

        if not offer.in_kt:
            # оффер есть только у нас; если он появился и в Keitaro, считаем его опубликованным
            if kt is not None:
                offer.in_kt = True
                offer.kt_weight = kt.weight
                offer.archived = False
                offer.was_archived = False
                offer.active = True
                items.append(_auto(
                    f"{offer.offer_id}:appeared_in_kt", offer.offer_id,
                    f"Оффер {offer.offer_id} тем временем появился и в Keitaro. Считаем его опубликованным.",
                ))
            continue

        if kt is None:
            _merge_removed_in_keitaro(offer, resolutions, items)
            continue

        # оффер остаётся в Keitaro: сверяем вес
        previous_weight = offer.kt_weight
        offer.kt_weight = kt.weight
        if kt.weight != previous_weight:
            _merge_weight_changed(offer, previous_weight, kt.weight, resolutions, items)

    # пересчитываем веса; если вес из Keitaro не помещается, оставляем расчёт черновика
    try:
        recalculate(offers)
    except WeightError:
        for offer in offers:
            if offer.temp_pinned:
                offer.pinned = False
                offer.temp_pinned = False
        items.append(_auto(
            "weights_overflow", 0,
            "Веса из Keitaro не помещаются в 100% вместе с закреплёнными. Оставили расчёт черновика.",
        ))
        recalculate(offers)

    logger.info("Merge: пунктов %s, нерешённых конфликтов %s", len(items), len([i for i in items if i.kind == "conflict" and i.resolution is None]))
    return MergeResult(offers=offers, items=items)


def _merge_removed_in_keitaro(offer: DraftOffer, resolutions: dict[str, str], items: list[MergeItem]) -> None:
    """Оффер исчез из Keitaro после загрузки."""
    if offer.active and offer.pinned:
        # пользователь закрепил вес, а оффер удалили в Keitaro: нужно решение
        key = f"{offer.offer_id}:pinned_removed_in_kt"
        item = _conflict(
            key, offer.offer_id,
            f"Оффер {offer.offer_id} удалён в Keitaro, а в черновике его вес закреплён ({offer.weight}%).",
            resolutions,
        )
        items.append(item)
        if item.resolution == "keitaro":
            _archive(offer)
        else:
            # оставляем оффер в черновике: при отправке он вернётся в Keitaro как новый
            offer.in_kt = False
            offer.kt_weight = 0
        return

    # оффер не закреплён или уже убран в черновике: он остаётся удалённым
    _archive(offer)
    items.append(_auto(
        f"{offer.offer_id}:removed_in_kt", offer.offer_id,
        f"Оффер {offer.offer_id} удалён в Keitaro. Оставляем его удалённым (он будет в архиве).",
    ))


def _merge_weight_changed(
    offer: DraftOffer, old_weight: int, new_weight: int, resolutions: dict[str, str], items: list[MergeItem]
) -> None:
    """В Keitaro изменили вес оффера после загрузки."""
    if not offer.active:
        # оффер убран в черновике, а в Keitaro у него изменили вес: нужно решение
        key = f"{offer.offer_id}:weight_changed_removed"
        item = _conflict(
            key, offer.offer_id,
            f"Оффер {offer.offer_id} убран в черновике, а в Keitaro у него изменили вес с {old_weight}% на {new_weight}%.",
            resolutions,
        )
        items.append(item)
        if item.resolution == "keitaro":
            offer.active = True
            offer.archived = False
            _fix_weight(offer, new_weight)
        return

    if offer.pinned:
        # закреплённый в черновике вес побеждает
        items.append(_auto(
            f"{offer.offer_id}:weight_changed_pinned", offer.offer_id,
            f"Вес оффера {offer.offer_id} изменён в Keitaro ({old_weight}% → {new_weight}%). Ваш закреплённый вес побеждает.",
        ))
        return

    # вес из Keitaro фиксируем, остальные доли пересчитаем
    _fix_weight(offer, new_weight)
    items.append(_auto(
        f"{offer.offer_id}:weight_changed", offer.offer_id,
        f"Вес оффера {offer.offer_id} изменён в Keitaro ({old_weight}% → {new_weight}%). Берём {new_weight}%, остальные пересчитаем.",
    ))
