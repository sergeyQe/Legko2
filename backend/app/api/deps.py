"""Зависимости FastAPI: сессия БД, клиент Keitaro и сервисы."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.keitaro.client import KeitaroClient
from app.keitaro.factory import get_keitaro_client
from app.keitaro.mock_client import MockKeitaroClient
from app.services.creator_service import CreatorService
from app.services.editor_service import EditorService
from app.services.reference_service import ReferenceService


def get_editor_service(
    session: Session = Depends(get_session), keitaro: KeitaroClient = Depends(get_keitaro_client)
) -> EditorService:
    """Сервис редактора на сессии текущего запроса."""
    return EditorService(session, keitaro)


def get_creator_service(keitaro: KeitaroClient = Depends(get_keitaro_client)) -> CreatorService:
    """Сервис создателя кампаний."""
    return CreatorService(keitaro)


def get_reference_service(
    keitaro: KeitaroClient = Depends(get_keitaro_client), settings: Settings = Depends(get_settings)
) -> ReferenceService:
    """Сервис справочников."""
    return ReferenceService(keitaro, settings)


def get_mock_client(keitaro: KeitaroClient = Depends(get_keitaro_client)) -> MockKeitaroClient:
    """Заглушка Keitaro для демонстрационных маршрутов; в режиме real их нет."""
    if not isinstance(keitaro, MockKeitaroClient):
        raise HTTPException(status_code=404, detail="Демонстрационные маршруты доступны только в режиме mock")
    return keitaro
