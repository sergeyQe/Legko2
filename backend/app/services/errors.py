"""Ошибки сервисного слоя."""
from app.domain.errors import DomainError
from app.domain.merge import MergeItem
from app.services.views import CreateReport


class EntityNotFoundError(DomainError):
    """Нашей сущности (кампании, потока, оффера) нет в БД."""

    def __init__(self, entity: str, entity_id: int):
        super().__init__(f"Не найдено: {entity} {entity_id}.")
        self.entity = entity  # тип сущности: campaign, stream, offer
        self.entity_id = entity_id  # ID сущности


class CreatePartialError(DomainError):
    """Создание кампании остановилось после создания кампании: часть шагов выполнена."""

    def __init__(self, report: "CreateReport"):
        super().__init__("Кампания создана не полностью. Кампанию мы не удаляем.")
        self.report = report  # отчёт по шагам


class MergeConflictError(DomainError):
    """При отправке есть спорные пункты без решения пользователя."""

    def __init__(self, conflicts: list[MergeItem]):
        super().__init__("Есть спорные изменения в Keitaro: выберите, какой вариант оставить.")
        self.conflicts = conflicts  # спорные пункты без решения
