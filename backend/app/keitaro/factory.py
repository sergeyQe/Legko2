"""Выбор клиента Keitaro по настройкам (mock или real)."""
import logging
from functools import lru_cache

from app.config import Settings, get_settings
from app.keitaro.client import KeitaroClient
from app.keitaro.http_client import HttpKeitaroClient
from app.keitaro.mock_client import MockKeitaroClient

logger = logging.getLogger(__name__)


def build_keitaro_client(settings: Settings) -> KeitaroClient:
    """Создаёт клиента: заглушку для mock или HTTP-клиента для real."""
    if settings.keitaro_mode == "mock":
        logger.info("Keitaro: режим mock (встроенная заглушка)")
        return MockKeitaroClient()

    # для real нужны адрес и ключ
    if not settings.keitaro_url or not settings.keitaro_api_key:
        raise ValueError("Для KEITARO_MODE=real нужно задать KEITARO_URL и KEITARO_API_KEY")
    logger.info("Keitaro: режим real (%s)", settings.keitaro_url)
    return HttpKeitaroClient(settings.keitaro_url, settings.keitaro_api_key, settings.keitaro_timeout_seconds)


@lru_cache
def get_keitaro_client() -> KeitaroClient:
    """Единый клиент на время работы процесса (важно для заглушки: она хранит данные в памяти)."""
    return build_keitaro_client(get_settings())
