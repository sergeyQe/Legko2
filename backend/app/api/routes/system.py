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
    summary="Получить сведения о сервисе",
    description=(
        "Возвращает версию сервиса, адрес Keitaro (для ссылки «Кампания в Keitaro») и префикс названий кампаний, "
        "с которыми работает сервис (кампании без него не показываются и не изменяются). "
        "Ключ Keitaro наружу не отдаётся. Ничего не меняет и не обращается к Keitaro."
    ),
)
def meta(settings: Settings = Depends(get_settings)) -> MetaOut:
    """Версия сервиса, адрес Keitaro и префикс кампаний."""
    return MetaOut(version=APP_VERSION, keitaro_url=settings.keitaro_url, campaign_prefix=settings.campaign_prefix)
