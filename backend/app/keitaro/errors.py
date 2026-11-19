"""Ошибки обращения к Keitaro. Клиент и тестовая заглушка бросают одни и те же исключения."""
from typing import Optional


class KeitaroError(Exception):
    """Базовая ошибка Keitaro."""

    def __init__(self, message: str = "", *, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message  # текст ошибки (поле error из ответа Keitaro как есть)
        self.status_code = status_code  # HTTP-статус ответа Keitaro, если он был


class KeitaroUnreachableError(KeitaroError):
    """Сеть недоступна, таймаут или ошибка сервера Keitaro (5xx)."""


class KeitaroAuthError(KeitaroError):
    """Ключ отклонён (401)."""


class KeitaroEditionError(KeitaroError):
    """Admin API недоступен в этой редакции Keitaro (402)."""


class KeitaroNotFoundError(KeitaroError):
    """Поток, кампания или оффер не найдены (404)."""

    def __init__(self, message: str = "", *, entity: str = "", entity_id: Optional[int] = None,
                 status_code: Optional[int] = 404):
        super().__init__(message, status_code=status_code)
        self.entity = entity  # что не найдено: stream, campaign, offer
        self.entity_id = entity_id  # ID того, что не найдено


class KeitaroRejectedError(KeitaroError):
    """Keitaro отклонил запрос (любой 4xx, кроме 401, 402 и 404)."""
