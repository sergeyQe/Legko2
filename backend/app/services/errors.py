"""Ошибки сервисного слоя."""
from app.domain.errors import DomainError
from app.domain.merge import MergeItem


class EntityNotFoundError(DomainError):
    """Нашей сущности (кампании, потока, оффера) нет в БД."""

    def __init__(self, entity: str, entity_id: int):
        super().__init__(f"Не найдено: {entity} {entity_id}.")
        self.entity = entity  # тип сущности: campaign, stream, offer
        self.entity_id = entity_id  # ID сущности


class MergeConflictError(DomainError):
    """При отправке есть спорные пункты без решения пользователя."""

    def __init__(self, conflicts: list[MergeItem]):
        super().__init__("Есть спорные изменения в Keitaro: выберите, какой вариант оставить.")
        self.conflicts = conflicts  # спорные пункты без решения
