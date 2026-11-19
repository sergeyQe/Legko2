"""Общие фикстуры тестов: БД SQLite в памяти (схема создаётся из моделей)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (регистрирует сущности в метаданных)
from app.db import Base


@pytest.fixture
def engine():
    """Движок SQLite в памяти; одно соединение на весь тест."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Сессия БД для теста."""
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def fake_kt():
    """Заглушка Keitaro для API-тестов."""
    from tests.fake_keitaro import FakeKeitaroClient

    return FakeKeitaroClient()


@pytest.fixture
def api(session, fake_kt):
    """HTTP-клиент приложения: БД SQLite в памяти и заглушка Keitaro вместо настоящих."""
    from fastapi.testclient import TestClient

    from app.config import Settings, get_settings
    from app.db import get_session
    from app.keitaro.factory import get_keitaro_client
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_keitaro_client] = lambda: fake_kt
    # настройки теста не зависят от локального .env: префикс «наших» кампаний и значения по умолчанию заданы явно
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, campaign_prefix="test_titov_", default_domain="kylovoa.com",
        default_group="FORTESTS", default_source="FORTESTS",
    )
    with TestClient(app) as client:
        yield client
