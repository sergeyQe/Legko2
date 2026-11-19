"""Зависимости FastAPI: сессия БД, клиент Keitaro и сервисы."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.keitaro.client import KeitaroClient
from app.keitaro.factory import get_keitaro_client
from app.services.creator_service import CreatorService
from app.services.editor_service import EditorService
from app.services.reference_service import ReferenceService


def get_editor_service(
    session: Session = Depends(get_session),
    keitaro: KeitaroClient = Depends(get_keitaro_client),
    settings: Settings = Depends(get_settings),
) -> EditorService:
    """Сервис редактора на сессии текущего запроса (работает только с кампаниями с префиксом из настроек)."""
    return EditorService(session, keitaro, settings.campaign_prefix)


def get_creator_service(
    keitaro: KeitaroClient = Depends(get_keitaro_client), settings: Settings = Depends(get_settings)
) -> CreatorService:
    """Сервис создателя кампаний (все названия получают префикс из настроек)."""
    return CreatorService(keitaro, settings.campaign_prefix)


def get_reference_service(
    keitaro: KeitaroClient = Depends(get_keitaro_client), settings: Settings = Depends(get_settings)
) -> ReferenceService:
    """Сервис справочников."""
    return ReferenceService(keitaro, settings)
