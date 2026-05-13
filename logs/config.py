import logging
import sys

from pythonjsonlogger import jsonlogger

from core.config import settings


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_json:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logging.basicConfig(level=settings.log_level.upper(), handlers=[handler], force=True)
