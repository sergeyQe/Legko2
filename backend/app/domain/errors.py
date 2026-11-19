"""Ошибки доменной логики (без привязки к HTTP, БД и Keitaro)."""


class DomainError(Exception):
    """Базовая ошибка бизнес-правил. Текст сообщения подходит для показа пользователю."""


class WeightError(DomainError, ValueError):
    """Веса нельзя распределить (например, сумма закреплённых больше 100%)."""


class OfferNotFoundError(DomainError):
    """Оффера с таким ID нет в потоке."""

    def __init__(self, offer_id: int):
        super().__init__(f"Оффер {offer_id} не найден в потоке.")
        self.offer_id = offer_id


class OfferAlreadyInStreamError(DomainError):
    """Оффер уже есть в потоке и активен."""

    def __init__(self, offer_id: int):
        super().__init__(f"Оффер {offer_id} уже есть в потоке.")
        self.offer_id = offer_id


class OfferRemovedError(DomainError):
    """Оффер есть в потоке в удалённом состоянии: его нужно вернуть, а не добавлять заново."""

    def __init__(self, offer_id: int):
        super().__init__(f"Оффер {offer_id} убран из потока. Нажмите «Вернуть в поток».")
        self.offer_id = offer_id


class OfferStateError(DomainError):
    """Действие невозможно в текущем состоянии оффера (например, убрать уже убранный)."""


class EmptyStreamError(DomainError):
    """Нельзя отправить в Keitaro поток без активных офферов."""

    def __init__(self) -> None:
        super().__init__("Нельзя отправить поток без активных офферов.")


class InvalidResolutionError(DomainError):
    """Решение по конфликту merge задано неверно."""
