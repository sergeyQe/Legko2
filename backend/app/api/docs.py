"""Описание ошибок для Swagger: коды из контракта API (этапы реализации, раздел 8.1)."""
from app.api.schemas import ErrorOut

# код ошибки -> (HTTP-статус, когда возвращается)
ERROR_CATALOG: dict[str, tuple[int, str]] = {
    "VALIDATION": (422, "неверный ввод (details.field — поле формы или details.errors — список ошибок)"),
    "WEIGHTS_INVALID": (422, "веса нельзя распределить (например, сумма закреплённых больше 100%)"),
    "EMPTY_STREAM": (422, "в потоке нет активных офферов, отправлять нечего"),
    "KEITARO_REJECTED": (422, "Keitaro отклонил запрос (details.keitaro_error — текст Keitaro как есть)"),
    "NOT_FOUND": (404, "кампания, поток или оффер не найдены в нашей БД (details.entity, details.id)"),
    "OFFER_STATE_ERROR": (409, "действие невозможно в текущем состоянии оффера (дубль, оффер убран и т.п.)"),
    "MERGE_CONFLICT": (409, "есть спорные изменения в Keitaro без решения (details.conflicts)"),
    "KEITARO_NOT_FOUND": (409, "Keitaro не нашёл поток или оффер: их могли удалить; загрузите потоки и повторите"),
    "KEITARO_UNREACHABLE": (502, "Keitaro не отвечает: сеть, таймаут или ошибка сервера; черновик сохранён"),
    "KEITARO_AUTH": (502, "Keitaro отклонил ключ доступа"),
    "KEITARO_EDITION": (502, "Admin API недоступен в этой редакции Keitaro"),
    "CREATE_PARTIAL": (502, "кампания создана не полностью (details.steps — результат каждого шага)"),
}

KEITARO_CODES = ("KEITARO_UNREACHABLE", "KEITARO_AUTH", "KEITARO_EDITION")


def responses(*codes: str) -> dict[int, dict]:
    """Блок responses для декоратора маршрута: объединяет коды ошибок по HTTP-статусам."""
    by_status: dict[int, list[str]] = {}
    for code in codes:
        status, text = ERROR_CATALOG[code]
        by_status.setdefault(status, []).append(f"`{code}`: {text}.")
    return {
        status: {"model": ErrorOut, "description": " ".join(lines)} for status, lines in sorted(by_status.items())
    }
