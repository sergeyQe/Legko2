"""Вспомогательные функции для тестов доменной логики."""
from app.domain.states import DraftOffer


def published(offer_id: int, weight: int) -> DraftOffer:
    """Опубликованный оффер: есть в Keitaro с указанным весом и активен в черновике."""
    return DraftOffer(
        offer_id=offer_id, name=f"Оффер {offer_id}", geo="XX",
        in_kt=True, kt_weight=weight, active=True, weight=weight,
    )


def screenshot_stream() -> list[DraftOffer]:
    """Поток 2 со скриншотов: три оффера 33/33/34."""
    return [published(11109, 33), published(11110, 33), published(11111, 34)]


def weights(offers: list[DraftOffer]) -> dict[int, int]:
    """Веса офферов по ID."""
    return {o.offer_id: o.weight for o in offers}
