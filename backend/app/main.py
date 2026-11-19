"""Точка входа FastAPI: сборка приложения."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import campaigns, creator, mock, references, streams, system
from app.config import get_settings
from app.keitaro.factory import get_keitaro_client
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {"name": "Служебные", "description": "Проверка работоспособности и режим работы сервиса."},
    {"name": "Кампании", "description": "Список кампаний, просмотр и загрузка потоков из Keitaro."},
    {"name": "Офферы потока", "description": "Действия над черновиком потока. Меняют только нашу БД, Keitaro не затрагивают."},
    {"name": "Предпросмотр и Push", "description": "Предпросмотр изменений и отправка потока в Keitaro."},
    {"name": "Создание кампании", "description": "Создание кампании с двумя потоками (публикуется в Keitaro сразу)."},
    {"name": "Справочники", "description": "Домены, группы, источники, поиск офферов."},
    {"name": "Демо (mock)", "description": "Имитация правок и сбоев Keitaro. Только при KEITARO_MODE=mock."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: при остановке закрываем соединения клиента Keitaro."""
    yield
    if get_keitaro_client.cache_info().currsize:
        get_keitaro_client().close()


def create_app() -> FastAPI:
    """Собирает приложение: логирование, CORS, middleware и маршруты."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="legko2 — обёртка над Keitaro",
        description="Редактор потоков (черновик → Push to KT) и создатель кампаний поверх Keitaro Admin API.",
        version=system.APP_VERSION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    register_exception_handlers(app)

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

    # подключаем маршруты; демонстрационные есть только в режиме mock
    for router in (system.router, campaigns.router, streams.offers_router, streams.push_router,
                   creator.router, references.router):
        app.include_router(router)
    if settings.keitaro_mode == "mock":
        app.include_router(mock.router)

    return app


app = create_app()
