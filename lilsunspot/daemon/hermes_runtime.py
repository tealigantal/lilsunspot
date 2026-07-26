from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

import yaml

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .hermes_config_migration import (
    HermesConfigMigrationError,
    ensure_hermes_config_ready,
    prepare_config_for_write,
)
from .provider_client import ProviderValidationError, validate_base_url_override
from .providers import load_provider_registry, provider_by_id


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


def _remove_env_keys(env_path: Path, keys: set[str]) -> int:
    cleaned_keys = {key for key in keys if key.replace("_", "").isalnum() and key.upper() == key}
    if not cleaned_keys or not env_path.exists():
        return 0

    lines = _read_env_lines(env_path)
    removed = 0
    out: list[str] = []
    for line in lines:
        name = line.partition("=")[0].strip()
        if name in cleaned_keys:
            removed += 1
            continue
        out.append(line)

    if not removed:
        return 0

    env_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    text = "\n".join(out).rstrip()
    tmp.write_text((text + "\n") if text else "", encoding="utf-8")
    tmp.replace(env_path)
    return removed


def _env_has_value(env_path: Path, key: str) -> bool:
    prefix = f"{key}="
    return any(line.startswith(prefix) and line.partition("=")[2].strip() for line in _read_env_lines(env_path))


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


def _product_auxiliary_default_base_url(
    provider_config: dict[str, Any] | None,
    provider_id: str,
    hermes_provider: str,
    provider_type: str,
) -> str:
    if provider_config is None:
        return ""
    base_url = str(provider_config.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        return ""
    if hermes_provider == "custom":
        return base_url
    if provider_type != "local" and provider_id != hermes_provider:
        return base_url
    return ""


def _apply_product_auxiliary_compat_defaults(config: dict[str, Any]) -> bool:
    auxiliary = config.get("auxiliary") if isinstance(config.get("auxiliary"), dict) else {}
    lilsunspot = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    product_auxiliary = lilsunspot.get("auxiliary") if isinstance(lilsunspot.get("auxiliary"), dict) else {}
    if not auxiliary or not product_auxiliary:
        return False

    changed = False
    for task_id, product_entry in product_auxiliary.items():
        if not isinstance(product_entry, dict):
            continue
        provider_id = str(product_entry.get("provider") or "").strip()
        provider_config = provider_by_id(provider_id) if provider_id else None
        hermes_provider = str((provider_config or {}).get("hermes_provider") or provider_id).strip()
        provider_type = str((provider_config or {}).get("type") or "cloud").strip().lower()
        default_base_url = _product_auxiliary_default_base_url(
            provider_config,
            provider_id,
            hermes_provider,
            provider_type,
        )
        if not default_base_url:
            continue

        hermes_entry = auxiliary.get(task_id)
        if isinstance(hermes_entry, dict) and str(hermes_entry.get("provider") or "").strip() == hermes_provider:
            if not str(hermes_entry.get("base_url") or "").strip():
                hermes_entry["base_url"] = default_base_url
                changed = True

        if not str(product_entry.get("base_url") or "").strip():
            product_entry["base_url"] = default_base_url
            changed = True

    return changed


def read_hermes_config(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    config_path = runtime_paths.hermes_home / "config.yaml"
    try:
        ensure_hermes_config_ready(runtime_paths)
    except HermesConfigMigrationError as exc:
        raise HermesRuntimeError(str(exc)) from exc
    config = _read_config(config_path)
    if _apply_product_auxiliary_compat_defaults(config):
        _write_config(config_path, config)
    return config


def write_hermes_config(config: dict[str, Any], paths: RuntimePaths | None = None) -> None:
    runtime_paths = paths or ensure_runtime_dirs()
    try:
        ensure_hermes_config_ready(runtime_paths)
        prepared = prepare_config_for_write(config)
    except HermesConfigMigrationError as exc:
        raise HermesRuntimeError(str(exc)) from exc
    _write_config(runtime_paths.hermes_home / "config.yaml", prepared)


def save_hermes_env_value(key: str, value: str, paths: RuntimePaths | None = None) -> None:
    runtime_paths = paths or ensure_runtime_dirs()
    _write_env_value(runtime_paths.hermes_home / ".env", key, value)


def clear_local_model_credentials(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    config = read_hermes_config(runtime_paths)
    env_keys = {
        str(provider.get("env_key") or "").strip()
        for provider in load_provider_registry()
        if str(provider.get("env_key") or "").strip()
    }
    removed_env_keys = _remove_env_keys(runtime_paths.hermes_home / ".env", env_keys)

    cleared_config_keys: list[str] = []
    for key in ("model", "fallback_providers", "provider_routing", "auxiliary"):
        if key in config:
            config.pop(key, None)
            cleared_config_keys.append(key)

    lilsunspot = config.get("lilsunspot")
    if isinstance(lilsunspot, dict):
        for key in ("provider", "model", "auxiliary", "capability_verification"):
            if key in lilsunspot:
                lilsunspot.pop(key, None)
        lilsunspot["reset_at"] = datetime.now(timezone.utc).isoformat()
        if not lilsunspot:
            config.pop("lilsunspot", None)

    write_hermes_config(config, runtime_paths)
    return {
        "removed_env_keys": removed_env_keys,
        "cleared_config_keys": sorted(cleared_config_keys),
    }


def _redact_config_value(value: Any) -> Any:
    sensitive = {"api_key", "apikey", "authorization", "password", "secret", "token", "bot_token"}
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in sensitive):
                redacted[key_text] = "[已隐藏]"
            else:
                redacted[key_text] = _redact_config_value(child)
        return redacted
    if isinstance(value, list):
        try:
            from .audit import redact_value

            return redact_value(value)
        except Exception:
            return [_redact_config_value(item) for item in value]
    if isinstance(value, str):
        try:
            from .audit import redact_text

            return redact_text(value)
        except Exception:
            return value
    return value


def _clear_capability_verification(config: dict[str, Any], capability_id: str) -> None:
    lilsunspot = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    verification = lilsunspot.get("capability_verification") if isinstance(lilsunspot.get("capability_verification"), dict) else {}
    verification.pop(capability_id, None)


def model_runtime_config(paths: RuntimePaths | None = None) -> dict[str, Any]:
    config = read_hermes_config(paths)
    model = config.get("model") if isinstance(config.get("model"), dict) else {}
    lilsunspot = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    return {
        "main": {
            "provider": str(model.get("provider") or ""),
            "model": str(model.get("default") or ""),
            "base_url": str(model.get("base_url") or ""),
        },
        "fallback_providers": _redact_config_value(config.get("fallback_providers") or []),
        "provider_routing": _redact_config_value(config.get("provider_routing") or {}),
        "auxiliary": _redact_config_value(config.get("auxiliary") or {}),
        "lilsunspot_auxiliary": _redact_config_value(lilsunspot.get("auxiliary") or {}),
        "compression": _redact_config_value(config.get("compression") or {}),
    }


def save_fallback_providers(fallbacks: list[dict[str, Any]], paths: RuntimePaths | None = None) -> dict[str, Any]:
    cleaned: list[dict[str, str]] = []
    for item in fallbacks:
        if not isinstance(item, dict):
            raise HermesRuntimeError("备用模型配置格式不正确。")
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or "").strip()
        base_url = str(item.get("base_url") or "").strip().rstrip("/")
        if not provider or not model:
            raise HermesRuntimeError("备用模型必须包含 provider 和 model。")
        entry = {"provider": provider, "model": model}
        if base_url:
            entry["base_url"] = base_url
        cleaned.append(entry)
    config = read_hermes_config(paths)
    config["fallback_providers"] = cleaned
    write_hermes_config(config, paths)
    return model_runtime_config(paths)


def save_provider_routing(routing: dict[str, Any], paths: RuntimePaths | None = None) -> dict[str, Any]:
    if not isinstance(routing, dict):
        raise HermesRuntimeError("模型路由配置格式不正确。")
    config = read_hermes_config(paths)
    config["provider_routing"] = routing
    write_hermes_config(config, paths)
    return model_runtime_config(paths)


def save_auxiliary_model(
    task: str,
    provider: str,
    model: str,
    base_url: str = "",
    api_key: str = "",
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    task_id = task.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", task_id):
        raise HermesRuntimeError("辅助模型任务名不合法。")
    config = read_hermes_config(paths)
    auxiliary = config.setdefault("auxiliary", {})
    if not isinstance(auxiliary, dict):
        auxiliary = {}
        config["auxiliary"] = auxiliary
    provider_id = provider.strip()
    provider_config = provider_by_id(provider_id)
    hermes_provider = str((provider_config or {}).get("hermes_provider") or provider_id).strip()
    env_key = str((provider_config or {}).get("env_key") or "").strip()
    provider_type = str((provider_config or {}).get("type") or "cloud").strip().lower()
    normalized_base_url = base_url.strip().rstrip("/")
    if provider_config is not None:
        try:
            normalized_base_url = validate_base_url_override(provider_config, normalized_base_url).strip().rstrip("/")
        except ProviderValidationError as exc:
            raise HermesRuntimeError(str(exc)) from exc
        if not normalized_base_url:
            normalized_base_url = _product_auxiliary_default_base_url(
                provider_config,
                provider_id,
                hermes_provider,
                provider_type,
            )

    api_key = api_key.strip()
    clearing_task = hermes_provider in {"", "auto"} and not model.strip() and not normalized_base_url and not api_key
    if clearing_task:
        auxiliary.pop(task_id, None)
        lilsunspot = config.setdefault("lilsunspot", {})
        if isinstance(lilsunspot, dict):
            lilsunspot_aux = lilsunspot.setdefault("auxiliary", {})
            if isinstance(lilsunspot_aux, dict):
                lilsunspot_aux.pop(task_id, None)
        if task_id == "vision":
            _clear_capability_verification(config, "image.read")
        write_hermes_config(config, paths)
        return model_runtime_config(paths)

    if hermes_provider in {"", "auto"}:
        raise HermesRuntimeError("请先选择图片识别服务。")
    if not model.strip():
        raise HermesRuntimeError("视觉模型名称不能为空。")

    if api_key:
        if not env_key:
            raise HermesRuntimeError("这个视觉模型服务暂不能保存 API Key。")
        _write_env_value(paths.hermes_home / ".env", env_key, api_key)

    if provider_config is not None and provider_type != "local" and not api_key and hermes_provider not in {"auto", "main"}:
        env_path = paths.hermes_home / ".env"
        has_existing_key = any(line.startswith(f"{env_key}=") and line.partition("=")[2].strip() for line in _read_env_lines(env_path))
        if not has_existing_key:
            raise HermesRuntimeError("请先填写这个视觉模型服务的 API Key。")

    entry: dict[str, str] = {
        "provider": hermes_provider,
        "model": model.strip(),
    }
    if normalized_base_url:
        entry["base_url"] = normalized_base_url
    auxiliary[task_id] = entry

    lilsunspot = config.setdefault("lilsunspot", {})
    if isinstance(lilsunspot, dict):
        lilsunspot_aux = lilsunspot.setdefault("auxiliary", {})
        if isinstance(lilsunspot_aux, dict):
            lilsunspot_aux[task_id] = {
                "provider": provider_id,
                "model": model.strip(),
                "base_url": normalized_base_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
    if task_id == "vision":
        _clear_capability_verification(config, "image.read")
    write_hermes_config(config, paths)
    return model_runtime_config(paths)


def _validate_mcp_name(name: str) -> str:
    normalized = name.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", normalized):
        raise HermesRuntimeError("MCP 服务名称只能包含字母、数字、点、下划线和短横线。")
    return normalized


def _clean_mcp_server(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HermesRuntimeError("MCP 配置格式不正确。")
    allowed = {"command", "args", "url", "transport", "enabled", "env", "headers", "tools", "auth"}
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "args":
            if not isinstance(value, list):
                raise HermesRuntimeError("MCP args 必须是列表。")
            cleaned[key] = [str(item) for item in value]
        elif key in {"env", "headers", "tools", "auth"}:
            if not isinstance(value, dict):
                raise HermesRuntimeError(f"MCP {key} 必须是对象。")
            cleaned[key] = value
        elif key == "enabled":
            cleaned[key] = bool(value)
        else:
            cleaned[key] = str(value).strip()
    if not cleaned.get("command") and not cleaned.get("url"):
        raise HermesRuntimeError("MCP 服务必须配置 command 或 url。")
    return cleaned


def list_mcp_servers(paths: RuntimePaths | None = None) -> dict[str, Any]:
    config = read_hermes_config(paths)
    servers = config.get("mcp_servers") if isinstance(config.get("mcp_servers"), dict) else {}
    public = {
        name: _redact_config_value(value if isinstance(value, dict) else {})
        for name, value in sorted(servers.items())
    }
    return {"servers": public}


def upsert_mcp_server(name: str, payload: dict[str, Any], paths: RuntimePaths | None = None) -> dict[str, Any]:
    server_name = _validate_mcp_name(name)
    cleaned = _clean_mcp_server(payload)
    config = read_hermes_config(paths)
    servers = config.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        servers = {}
        config["mcp_servers"] = servers
    servers[server_name] = cleaned
    write_hermes_config(config, paths)
    return list_mcp_servers(paths)


def delete_mcp_server(name: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    server_name = _validate_mcp_name(name)
    config = read_hermes_config(paths)
    servers = config.setdefault("mcp_servers", {})
    if isinstance(servers, dict):
        servers.pop(server_name, None)
    write_hermes_config(config, paths)
    return list_mcp_servers(paths)


def save_provider_credentials(
    provider_config: dict[str, Any],
    model: str,
    api_key: str,
    base_url_override: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, str]:
    paths = paths or ensure_runtime_dirs()
    provider_id = str(provider_config.get("id") or "").strip()
    hermes_provider = str(provider_config.get("hermes_provider") or provider_id).strip()
    env_key = str(provider_config.get("env_key") or "").strip()
    try:
        base_url = validate_base_url_override(provider_config, base_url_override)
    except ProviderValidationError as exc:
        raise HermesRuntimeError(str(exc)) from exc
    if not base_url:
        base_url = str(provider_config.get("base_url") or "").strip()
    provider_type = str(provider_config.get("type") or "cloud").strip().lower()
    model = model.strip()
    api_key = api_key.strip()

    if not provider_id:
        raise HermesRuntimeError("Provider 缺少 id。")
    if not hermes_provider:
        raise HermesRuntimeError("Provider 缺少 Hermes provider 映射。")
    if not model:
        raise HermesRuntimeError("模型名称不能为空。")
    if not env_key:
        raise HermesRuntimeError("Provider 缺少 env_key，Day1 暂不能保存。")

    env_path = paths.hermes_home / ".env"
    config_path = paths.hermes_home / "config.yaml"
    if not api_key and provider_type != "local" and not _env_has_value(env_path, env_key):
        raise HermesRuntimeError("API Key 不能为空。")

    if api_key:
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
    existing_lilsunspot = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    config["lilsunspot"] = {
        **existing_lilsunspot,
        "provider": provider_id,
        "model": model,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _clear_capability_verification(config, "image.read")
    _write_config(config_path, config)

    return {
        "env_path": str(env_path),
        "config_path": str(config_path),
        "provider": provider_id,
        "model": model,
    }
