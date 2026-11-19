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
