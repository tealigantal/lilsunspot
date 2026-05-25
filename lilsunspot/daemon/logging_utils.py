from __future__ import annotations

import logging
import re
from pathlib import Path


_LOGGER_NAME = "lilsunspot.daemon"
_CONFIGURED = False


_TOKEN_RE = re.compile(r"([A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]{12,}([A-Za-z0-9_\-]{4})")


def redact_secret(value: str | None) -> str:
    if not value:
        return ""
    return _TOKEN_RE.sub(r"\1...\2", str(value))


def configure_logging(logs_dir: Path) -> logging.Logger:
    global _CONFIGURED

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if _CONFIGURED:
        return logger

    logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(logs_dir / "lilsunspotd.log", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)
