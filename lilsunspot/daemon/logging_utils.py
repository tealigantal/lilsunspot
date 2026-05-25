from __future__ import annotations

import logging
import re
from pathlib import Path


_LOGGER_NAME = "lilsunspot.daemon"
_CONFIGURED = False

_SECRET_TOKEN_RE = re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9_\-]{8,}\b")
_ENV_ASSIGNMENT_RE = re.compile(
    r"\b("
    r"DEEPSEEK_API_KEY|"
    r"OPENAI_API_KEY|"
    r"OPENROUTER_API_KEY|"
    r"KIMI_API_KEY|"
    r"DASHSCOPE_API_KEY"
    r")=([^\s'\";]+)"
)


def mask_secret(secret: str | None) -> str:
    value = str(secret or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "[redacted]"
    return f"{value[:3]}...{value[-4:]}"


def redact_text(text: object) -> str:
    value = str(text)

    def replace_token(match: re.Match[str]) -> str:
        return mask_secret(match.group(0))

    def replace_env(match: re.Match[str]) -> str:
        return f"{match.group(1)}={mask_secret(match.group(2))}"

    value = _SECRET_TOKEN_RE.sub(replace_token, value)
    value = _ENV_ASSIGNMENT_RE.sub(replace_env, value)
    return value


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


def configure_logging(logs_dir: Path) -> logging.Logger:
    global _CONFIGURED

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if _CONFIGURED:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(logs_dir / "lilsunspotd.log", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)
