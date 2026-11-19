"""Точка входа FastAPI: сборка приложения."""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {"name": "Служебные", "description": "Проверка работоспособности и режим работы сервиса."},
]


def create_app() -> FastAPI:
    """Собирает приложение: логирование, CORS, middleware и маршруты."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="legko2 — обёртка над Keitaro",
        description="Редактор потоков (черновик → Push to KT) и создатель кампаний поверх Keitaro Admin API.",
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
    )

    # разрешаем запросы фронтенда с другого порта
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Пишет в лог метод, путь, статус и время каждого запроса."""
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("%s %s -> %s (%.0f мс)", request.method, request.url.path, response.status_code, elapsed_ms)
        return response

    @app.get(
        "/health",
        tags=["Служебные"],
        summary="Проверить, что сервис работает",
        description=(
            "Возвращает `{\"status\": \"ok\"}`, если приложение запущено. "
            "Не обращается ни к базе данных, ни к Keitaro, ничего не меняет."
        ),
    )
    def health() -> dict[str, str]:
        """Проверка живости сервиса."""
        return {"status": "ok"}

    return app


app = create_app()
