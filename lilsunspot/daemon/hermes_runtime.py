from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .config_paths import RuntimePaths, ensure_runtime_dirs


class HermesRuntimeError(RuntimeError):
    """Raised when lilsunspot cannot safely write Hermes-compatible config."""


def _reject_multiline_secret(value: str) -> None:
    if "\n" in value or "\r" in value:
        raise HermesRuntimeError("API Key 不能包含换行符。")


def _read_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines()


def _write_env_value(env_path: Path, key: str, value: str) -> None:
    _reject_multiline_secret(value)
    if not key.replace("_", "").isalnum() or not key.upper() == key:
        raise HermesRuntimeError(f"Provider env_key 不合法: {key}")

    lines = _read_env_lines(env_path)
    prefix = f"{key}="
    updated = False
    out: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            if not updated:
                out.append(f"{key}={value}")
                updated = True
            continue
        out.append(line)
    if not updated:
        out.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    tmp.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    tmp.replace(env_path)


def _read_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_config(config_path: Path, config: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    tmp.replace(config_path)


def save_provider_credentials(
    provider_config: dict[str, Any],
    model: str,
    api_key: str,
    paths: RuntimePaths | None = None,
) -> dict[str, str]:
    paths = paths or ensure_runtime_dirs()
    provider_id = str(provider_config.get("id") or "").strip()
    hermes_provider = str(provider_config.get("hermes_provider") or provider_id).strip()
    env_key = str(provider_config.get("env_key") or "").strip()
    base_url = str(provider_config.get("base_url") or "").strip()
    model = model.strip()
    api_key = api_key.strip()

    if not provider_id:
        raise HermesRuntimeError("Provider 缺少 id。")
    if not hermes_provider:
        raise HermesRuntimeError("Provider 缺少 Hermes provider 映射。")
    if not model:
        raise HermesRuntimeError("模型名称不能为空。")
    if not api_key:
        raise HermesRuntimeError("API Key 不能为空。")
    if not env_key:
        raise HermesRuntimeError("Provider 缺少 env_key，Day1 暂不能保存。")

    env_path = paths.hermes_home / ".env"
    config_path = paths.hermes_home / "config.yaml"

    _write_env_value(env_path, env_key, api_key)

    config = _read_config(config_path)
    current_model = config.get("model")
    if isinstance(current_model, dict):
        model_config = dict(current_model)
    elif isinstance(current_model, str) and current_model.strip():
        model_config = {"default": current_model.strip()}
    else:
        model_config = {}

    model_config["provider"] = hermes_provider
    model_config["default"] = model
    if base_url:
        model_config["base_url"] = base_url.rstrip("/")
    else:
        model_config.pop("base_url", None)
    model_config.pop("api_key", None)

    config["model"] = model_config
    config["lilsunspot"] = {
        "provider": provider_id,
        "model": model,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_config(config_path, config)

    return {
        "env_path": str(env_path),
        "config_path": str(config_path),
        "provider": provider_id,
        "model": model,
    }
