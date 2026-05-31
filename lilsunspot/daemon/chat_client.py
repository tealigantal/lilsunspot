from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .providers import provider_by_id


CHAT_ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "setup_required": ("请先完成首启向导。", "打开 Provider 页，保存一个模型服务商配置。"),
    "provider_required": ("请先完成模型配置。", "在 Provider 页选择服务商和模型后保存。"),
    "missing_api_key": ("请先填写 API Key。", "重新配置模型并保存 API Key。本地模型可留空。"),
}


def _chat_error(error_code: str) -> dict[str, Any]:
    message, suggestion = CHAT_ERROR_MESSAGES[error_code]
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
        "suggestion": suggestion,
    }


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def current_runtime_model(paths: RuntimePaths | None = None) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    config = _read_yaml(paths.hermes_home / "config.yaml")
    lilsunspot_config = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    model_config = config.get("model") if isinstance(config.get("model"), dict) else {}

    provider = str(lilsunspot_config.get("provider") or "").strip()
    model = str(lilsunspot_config.get("model") or model_config.get("default") or "").strip()
    return {
        "configured": bool(provider and model),
        "provider": provider,
        "model": model,
    }


def _load_chat_settings(paths: RuntimePaths) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    config_path = paths.hermes_home / "config.yaml"
    if not config_path.exists():
        return _chat_error("setup_required"), None

    config = _read_yaml(config_path)
    lilsunspot_config = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    model_config = config.get("model") if isinstance(config.get("model"), dict) else {}
    provider_id = str(lilsunspot_config.get("provider") or "").strip()
    model = str(lilsunspot_config.get("model") or model_config.get("default") or "").strip()

    if not provider_id or not model:
        return _chat_error("provider_required"), None

    provider_config = provider_by_id(provider_id)
    if provider_config is None:
        return _chat_error("provider_required"), None

    env_key = str(provider_config.get("env_key") or "").strip()
    provider_type = str(provider_config.get("type") or "cloud").strip().lower()
    api_key = _read_env(paths.hermes_home / ".env").get(env_key, "").strip()
    if not api_key and provider_type != "local":
        return _chat_error("missing_api_key"), None

    return None, {
        "provider": str(provider_config["id"]),
        "model": model,
        "provider_type": provider_type,
    }


async def send_chat_message(
    message: str,
    conversation_id: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    del conversation_id
    del message
    paths = paths or ensure_runtime_dirs()
    error, settings = _load_chat_settings(paths)
    if error is not None:
        return error
    assert settings is not None

    return {
        "ok": True,
        "reply": "小黑子聊天骨架已收到消息。当前版本不会调用真实模型服务。",
        "engine": "placeholder",
        "provider": settings["provider"],
        "model": settings["model"],
    }
