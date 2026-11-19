"""Расчёт весов офферов потока с учётом закреплённых (pin) весов."""
import logging
from typing import Optional, Sequence

from app.domain.errors import WeightError

logger = logging.getLogger(__name__)

TOTAL_WEIGHT = 100  # сумма весов активных офферов потока, %


def calculate_weights(pins: Sequence[Optional[int]]) -> list[int]:
    """Возвращает вес каждого активного оффера в том же порядке, что и pins.

    pins[i] — закреплённый вес оффера или None, если оффер свободный.
    Свободные офферы делят остаток поровну, лишние проценты уходят последнему свободному (33/33/34).
    """
    # пустой поток — распределять нечего
    if not pins:
        return []

    # закреплённые веса должны быть в диапазоне 0..100
    pinned_sum = 0
    for pin in pins:
        if pin is None:
            continue
        if pin < 0 or pin > TOTAL_WEIGHT:
            raise WeightError(f"Закреплённый вес {pin}% вне диапазона 0..{TOTAL_WEIGHT}")
        pinned_sum += pin

    free_count = sum(1 for pin in pins if pin is None)

    # сумма закреплённых не должна превышать 100%
    if pinned_sum > TOTAL_WEIGHT:
        raise WeightError(
            f"Сумма закреплённых весов {pinned_sum}% больше {TOTAL_WEIGHT}%. Открепите вес хотя бы одного оффера."
        )

    # если свободных нет, закреплённые обязаны дать ровно 100%
    if free_count == 0:
        if pinned_sum != TOTAL_WEIGHT:
            raise WeightError(
                f"Все офферы закреплены, сумма {pinned_sum}% вместо {TOTAL_WEIGHT}%. "
                "Открепите вес хотя бы одного оффера."
            )
        return [int(pin) for pin in pins]  # type: ignore[arg-type]

    # остаток делим поровну между свободными, лишнее — последнему свободному
    remainder = TOTAL_WEIGHT - pinned_sum
    share, extra = divmod(remainder, free_count)
    result: list[int] = []
    free_seen = 0
    for pin in pins:
        if pin is not None:
            result.append(pin)
            continue
        free_seen += 1
        result.append(share + (extra if free_seen == free_count else 0))

    logger.debug("Веса рассчитаны: pins=%s -> %s", list(pins), result)
    return result
