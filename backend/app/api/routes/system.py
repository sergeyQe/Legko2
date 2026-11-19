"""Служебные маршруты: проверка работы и режим сервиса."""
from fastapi import APIRouter, Depends

from app.api.schemas import MetaOut
from app.config import Settings, get_settings

router = APIRouter(tags=["Служебные"])

APP_VERSION = "0.1.0"


@router.get(
    "/health",
    summary="Проверить, что сервис работает",
    description=(
        "Возвращает `{\"status\": \"ok\"}`, если приложение запущено. "
        "Не обращается ни к базе данных, ни к Keitaro, ничего не меняет."
    ),
)
def health() -> dict[str, str]:
    """Проверка живости сервиса."""
    return {"status": "ok"}


@router.get(
    "/meta",
    response_model=MetaOut,
    summary="Узнать режим работы сервиса",
    description=(
        "Возвращает режим Keitaro: `mock` (встроенная заглушка с данными из скриншотов) или `real` "
        "(настоящий Admin API). Фронтенд по этому полю решает, показывать ли демо-панель. "
        "Ничего не меняет и не обращается к Keitaro."
    ),
)
def meta(settings: Settings = Depends(get_settings)) -> MetaOut:
    """Режим работы сервиса и версия."""
    return MetaOut(mode=settings.keitaro_mode, version=APP_VERSION)
