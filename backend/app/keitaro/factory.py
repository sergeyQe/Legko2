"""Создание клиента Keitaro по настройкам."""
import logging
from functools import lru_cache

from app.config import Settings, get_settings
from app.keitaro.client import KeitaroClient
from app.keitaro.http_client import HttpKeitaroClient

logger = logging.getLogger(__name__)


def build_keitaro_client(settings: Settings) -> KeitaroClient:
    """Создаёт HTTP-клиента настоящего Keitaro; адрес и ключ обязательны."""
    if not settings.keitaro_url or not settings.keitaro_api_key:
        raise ValueError("Задайте KEITARO_URL и KEITARO_API_KEY (адрес и ключ Admin API Keitaro)")
    logger.info("Keitaro: %s", settings.keitaro_url)
    return HttpKeitaroClient(settings.keitaro_url, settings.keitaro_api_key, settings.keitaro_timeout_seconds)


@lru_cache
def get_keitaro_client() -> KeitaroClient:
    """Единый клиент на время работы процесса."""
    return build_keitaro_client(get_settings())
