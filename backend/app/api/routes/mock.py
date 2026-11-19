"""Демонстрационные маршруты (только KEITARO_MODE=mock): правки и сбои «со стороны» Keitaro.

Правки и сбои меняют только состояние заглушки Keitaro; сброс (/mock/reset) дополнительно очищает нашу копию.
"""
import logging

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_mock_client
from app.api.docs import responses
from app.api.schemas import ExternalChangeBody, FailureBody
from app.db import get_session
from app.keitaro.mock_client import MockKeitaroClient
from app.models import Campaign

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mock", tags=["Демо (mock)"])


@router.post(
    "/external-change",
    summary="Имитировать правку в Keitaro",
    description=(
        "Меняет данные заглушки так, будто пользователь вручную поправил поток в Keitaro: добавил оффер, изменил вес "
        "или удалил оффер. Обёртка узнает об этом при загрузке потоков или при отправке (объединение). "
        "Доступно только в режиме `mock`; нашу БД не меняет."
    ),
    responses=responses("KEITARO_NOT_FOUND", "KEITARO_REJECTED"),
)
def external_change(
    body: ExternalChangeBody = Body(), client: MockKeitaroClient = Depends(get_mock_client)
) -> dict[str, str]:
    """Имитация правки в Keitaro."""
    logger.info("[mock] внешняя правка: %s", body.model_dump())
    if body.scenario == "offer_added":
        client.external_offer_added(body.stream_id, body.offer_id, body.weight)
    elif body.scenario == "weight_changed":
        client.external_weight_changed(body.stream_id, body.offer_id, body.weight)
    else:
        client.external_offer_removed(body.stream_id, body.offer_id)
    return {"status": "ok"}


@router.post(
    "/failure",
    summary="Запланировать сбой Keitaro",
    description=(
        "Следующие `times` вызовов выбранной операции заглушки завершатся ошибкой заданного вида (сеть, ключ, редакция, "
        "не найдено, отказ Keitaro). После этого операция снова работает. Данные заглушки сбой не меняет. "
        "Доступно только в режиме `mock`."
    ),
)
def plan_failure(body: FailureBody = Body(), client: MockKeitaroClient = Depends(get_mock_client)) -> dict[str, str]:
    """Планирование сбоя."""
    logger.info("[mock] планируется сбой: %s", body.model_dump())
    client.fail_next(body.kind, body.target, body.times)
    return {"status": "ok"}


@router.post(
    "/reset",
    summary="Сбросить демонстрацию к исходному состоянию",
    description=(
        "Возвращает данные заглушки Keitaro к исходным (по скриншотам), снимает все запланированные сбои и очищает "
        "нашу копию: кампании, потоки и черновики. Так наша БД не расходится с заглушкой, которая хранится в памяти "
        "и сама сбрасывается при перезапуске сервера. После сброса кампании нужно загрузить из Keitaro заново. "
        "Доступно только в режиме `mock`."
    ),
)
def reset(
    client: MockKeitaroClient = Depends(get_mock_client), session: Session = Depends(get_session)
) -> dict[str, str]:
    """Сброс заглушки и нашей копии данных."""
    client.reset()
    # удаляем кампании через ORM, чтобы каскадно удалились потоки и офферы
    for campaign in session.scalars(select(Campaign)).all():
        session.delete(campaign)
    session.commit()
    logger.info("[mock] сброс: данные заглушки и наша копия очищены")
    return {"status": "ok"}


@router.get(
    "/state",
    summary="Показать состояние заглушки Keitaro",
    description=(
        "Возвращает кампании, потоки, офферы и запланированные сбои заглушки для отладки. "
        "Ничего не меняет. Доступно только в режиме `mock`."
    ),
)
def state(client: MockKeitaroClient = Depends(get_mock_client)) -> dict:
    """Состояние заглушки."""
    return client.describe()
