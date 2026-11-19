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
def mock_kt():
    """Заглушка Keitaro для API-тестов."""
    from app.keitaro.mock_client import MockKeitaroClient

    return MockKeitaroClient()


@pytest.fixture
def api(session, mock_kt):
    """HTTP-клиент приложения: БД SQLite в памяти и заглушка Keitaro вместо настоящих."""
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.keitaro.factory import get_keitaro_client
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_keitaro_client] = lambda: mock_kt
    with TestClient(app) as client:
        yield client
