"""Перевод исключений в единый формат ответа {code, message, details}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.domain.errors import (
    DomainError,
    EmptyStreamError,
    InvalidResolutionError,
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    OfferRemovedError,
    OfferStateError,
    ValidationError,
    WeightError,
)
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroEditionError,
    KeitaroError,
    KeitaroNotFoundError,
    KeitaroRejectedError,
    KeitaroUnreachableError,
)
from app.services.errors import CreatePartialError, EntityNotFoundError, MergeConflictError

logger = logging.getLogger(__name__)


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    """Тело ответа с ошибкой."""
    return {"code": code, "message": message, "details": details or {}}


def describe_domain_error(exc: DomainError) -> tuple[int, dict]:
    """HTTP-статус и тело ответа для ошибки бизнес-правил."""
    if isinstance(exc, ValidationError):
        return 422, error_body("VALIDATION", str(exc), {"field": exc.field})
    if isinstance(exc, InvalidResolutionError):
        return 422, error_body("VALIDATION", str(exc), {"field": "resolutions"})
    if isinstance(exc, WeightError):
        return 422, error_body("WEIGHTS_INVALID", str(exc))
    if isinstance(exc, EmptyStreamError):
        return 422, error_body("EMPTY_STREAM", str(exc))
    if isinstance(exc, EntityNotFoundError):
        return 404, error_body("NOT_FOUND", str(exc), {"entity": exc.entity, "id": exc.entity_id})
    if isinstance(exc, OfferNotFoundError):
        return 404, error_body("NOT_FOUND", str(exc), {"entity": "offer", "id": exc.offer_id})
    if isinstance(exc, (OfferAlreadyInStreamError, OfferRemovedError)):
        return 409, error_body("OFFER_STATE_ERROR", str(exc), {"offer_id": exc.offer_id})
    if isinstance(exc, OfferStateError):
        return 409, error_body("OFFER_STATE_ERROR", str(exc))
    if isinstance(exc, MergeConflictError):
        conflicts = [{"key": c.key, "offer_id": c.offer_id, "message": c.message} for c in exc.conflicts]
        return 409, error_body("MERGE_CONFLICT", str(exc), {"conflicts": conflicts})
    if isinstance(exc, CreatePartialError):
        report = exc.report
        steps = [{"name": s.name, "description": s.description, "status": s.status, "error": s.error} for s in report.steps]
        details = {"steps": steps, "campaign_id": report.campaign_id, "name": report.name, "alias": report.alias}
        return 502, error_body("CREATE_PARTIAL", str(exc), details)
    return 400, error_body("DOMAIN_ERROR", str(exc))


def describe_keitaro_error(exc: KeitaroError) -> tuple[int, dict]:
    """HTTP-статус и тело ответа для ошибки Keitaro."""
    if isinstance(exc, KeitaroUnreachableError):
        return 502, error_body(
            "KEITARO_UNREACHABLE", "Keitaro не отвечает. Попробуйте ещё раз, сохранённые изменения не потеряются.",
            {"retryable": True},
        )
    if isinstance(exc, KeitaroAuthError):
        return 502, error_body("KEITARO_AUTH", "Keitaro отклонил ключ доступа. Проверьте ключ в настройках сервиса.")
    if isinstance(exc, KeitaroEditionError):
        return 502, error_body("KEITARO_EDITION", "Admin API недоступен в этой редакции Keitaro.")
    if isinstance(exc, KeitaroNotFoundError):
        return 409, error_body(
            "KEITARO_NOT_FOUND", "Keitaro не нашёл объект: возможно, его удалили. Загрузите потоки из KT и повторите.",
            {"entity": exc.entity, "id": exc.entity_id},
        )
    if isinstance(exc, KeitaroRejectedError):
        return 422, error_body(
            "KEITARO_REJECTED", f"Keitaro отклонил запрос. Причина: {exc.message}", {"keitaro_error": exc.message}
        )
    return 502, error_body("KEITARO_ERROR", "Ошибка при обращении к Keitaro.", {"keitaro_error": exc.message})


def _json(status: int, body: dict) -> JSONResponse:
    return JSONResponse(status_code=status, content=body)


# русские тексты для типичных ошибок проверки полей (ключ — тип ошибки pydantic)
_VALIDATION_TEXTS = {
    "missing": "Поле обязательно.",
    "int_parsing": "Нужно целое число.",
    "int_type": "Нужно целое число.",
    "greater_than": "Значение слишком маленькое.",
    "greater_than_equal": "Значение слишком маленькое.",
    "less_than": "Значение слишком большое.",
    "less_than_equal": "Значение слишком большое.",
    "string_type": "Нужен текст.",
    "string_too_long": "Текст слишком длинный.",
    "bool_parsing": "Нужно значение «да» или «нет».",
    "bool_type": "Нужно значение «да» или «нет».",
    "literal_error": "Недопустимое значение.",
    "json_invalid": "Неверный формат данных.",
    "model_attributes_type": "Неверный формат данных.",
    "dict_type": "Неверный формат данных.",
}


def _validation_message(error: dict) -> str:
    """Русский текст ошибки поля (для незнакомых типов остаётся текст pydantic)."""
    return _VALIDATION_TEXTS.get(error.get("type", ""), str(error.get("msg", "Неверное значение.")))


def register_exception_handlers(app: FastAPI) -> None:
    """Подключает обработчики ошибок к приложению."""

    @app.exception_handler(DomainError)
    async def domain_handler(request: Request, exc: DomainError) -> JSONResponse:
        status, body = describe_domain_error(exc)
        logger.log(logging.WARNING if status >= 500 else logging.INFO, "%s %s -> %s %s", request.method, request.url.path, status, body["code"])
        return _json(status, body)

    @app.exception_handler(KeitaroError)
    async def keitaro_handler(request: Request, exc: KeitaroError) -> JSONResponse:
        status, body = describe_keitaro_error(exc)
        logger.warning("%s %s -> %s %s (%s)", request.method, request.url.path, status, body["code"], exc.message)
        return _json(status, body)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or "body", "message": _validation_message(e)}
            for e in exc.errors()
        ]
        return _json(422, error_body("VALIDATION", "Проверьте введённые данные.", {"errors": errors}))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # служебные ответы фреймворка (неизвестный адрес, неверный метод) приводим к нашему формату
        generic = {404: ("NOT_FOUND", "Такого адреса нет."), 405: ("METHOD_NOT_ALLOWED", "Этот метод здесь не поддерживается.")}
        code, message = generic.get(exc.status_code, ("HTTP_ERROR", "Не удалось выполнить запрос."))
        detail = exc.detail if isinstance(exc.detail, str) else ""
        if detail and detail not in ("Not Found", "Method Not Allowed"):
            message = detail  # наш собственный текст (например, у демо-маршрутов вне режима mock)
        return _json(exc.status_code, error_body(code, message))

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка: %s %s", request.method, request.url.path)
        response = _json(500, error_body("INTERNAL_ERROR", "Внутренняя ошибка сервиса. Подробности в журнале."))
        # этот ответ идёт мимо CORS-обработчика: без заголовка браузер покажет «заблокировано CORS» вместо нашей ошибки
        origin = request.headers.get("origin")
        if origin and origin in get_settings().cors_origin_list:
            response.headers["access-control-allow-origin"] = origin
            response.headers["vary"] = "Origin"
        return response
