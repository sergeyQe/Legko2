"""Настройки приложения из переменных окружения и файла .env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки сервиса. Секреты (ключ Keitaro, пароль БД) берутся только из окружения."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),  # корневой .env и локальный .env в папке backend
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://legko2:legko2@localhost:5432/legko2",
        description="Строка подключения SQLAlchemy к PostgreSQL",
    )
    keitaro_url: str = Field(default="", description="Адрес Keitaro, например https://kt.example.com")
    keitaro_api_key: str = Field(default="", description="Ключ Admin API (заголовок Api-Key)")
    keitaro_timeout_seconds: float = Field(default=10.0, description="Таймаут запроса к Keitaro, сек")
    campaign_prefix: str = Field(
        default="",
        description=(
            "Префикс названий кампаний, с которыми работает сервис, например test_titov_. "
            "Стенд Keitaro общий: кампании без этого префикса не показываются и не изменяются, "
            "а новые кампании получают его автоматически. Обязателен."
        ),
    )

    default_domain: str = Field(default="kylovoa.com", description="Домен по умолчанию для новой кампании")
    default_group: str = Field(default="FORTESTS", description="Группа по умолчанию для новой кампании")
    default_source: str = Field(default="FORTESTS", description="Источник трафика по умолчанию")

    log_level: str = Field(default="INFO", description="Уровень логирования: DEBUG, INFO, WARNING, ERROR")
    cors_origins: str = Field(
        default="http://localhost:5173", description="Разрешённые источники CORS через запятую"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Список источников CORS без пустых значений."""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Возвращает единый экземпляр настроек (кэшируется на время работы процесса)."""
    return Settings()
