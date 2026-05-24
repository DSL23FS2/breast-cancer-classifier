"""Вспомогательные функции: конфигурация, логгирование, метрики."""
import configparser
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def get_logger(name: str) -> logging.Logger:
    """Создать логгер с форматом timestamp + level + message."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def read_config(path: str | Path | None = None) -> configparser.ConfigParser:
    """Прочитать config.ini. По умолчанию — корень проекта."""
    cfg = configparser.ConfigParser()
    config_path = Path(path) if path else ROOT / "config.ini"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    cfg.read(config_path, encoding="utf-8")
    return cfg
