"""Настройка логирования: вывод в stdout, уровень из настроек."""
import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Включает логирование в stdout. Повторный вызов заменяет предыдущие обработчики."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # шумные сторонние библиотеки не засоряют DEBUG нашего кода
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
