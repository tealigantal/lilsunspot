from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from .logging_utils import redact_text


RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
PROVIDER_REGISTRY_FILE = RESOURCE_DIR / "provider_registry.yaml"
MODE_PROFILES_FILE = RESOURCE_DIR / "default_mode_profiles.yaml"
SAFETY_POLICY_FILE = RESOURCE_DIR / "default_safety_policy.yaml"

PUBLIC_PROVIDER_FIELDS = {
    "id",
    "display_name",
    "type",
    "key_url",
    "detect_url",
    "default_model",
    "env_key",
    "notes",
    "base_url",
}


def load_yaml_resource(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_provider_registry() -> list[dict[str, Any]]:
    data = load_yaml_resource(PROVIDER_REGISTRY_FILE)
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, list):
        raise ValueError("provider_registry.yaml must contain a providers list")
    return [dict(provider) for provider in providers if isinstance(provider, dict)]


def public_provider(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        key: provider.get(key)
        for key in PUBLIC_PROVIDER_FIELDS
        if key in provider and provider.get(key) is not None
    }


def public_provider_registry() -> list[dict[str, Any]]:
    return [public_provider(provider) for provider in load_provider_registry()]


def provider_by_id(provider_id: str) -> dict[str, Any] | None:
    normalized = provider_id.strip().lower()
    for provider in load_provider_registry():
        if str(provider.get("id", "")).strip().lower() == normalized:
            return provider
    return None


def required_resource_files() -> list[Path]:
    return [PROVIDER_REGISTRY_FILE, MODE_PROFILES_FILE, SAFETY_POLICY_FILE]


def validate_key_format(provider_config: dict[str, Any], api_key: str | None) -> tuple[bool, str]:
    provider_id = str(provider_config.get("id") or "").strip()
    provider_type = str(provider_config.get("type") or "").strip().lower()
    value = str(api_key or "").strip()

    if provider_id == "ollama" and not value:
        return True, "Ollama local detection does not require an API key."
    if not value:
        return False, "API key is required for this provider."
    if "\n" in value or "\r" in value:
        return False, "API key must be a single line."
    if any(char.isspace() for char in value):
        return False, "API key cannot contain spaces."
    if len(value) < 8:
        return False, "API key looks too short."
    if provider_type == "cloud" and value.lower() in {"test", "password", "changeme"}:
        return False, "API key looks like a placeholder."
    return True, "API key format looks valid."


def _response_body(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return redact_text(body)


def classify_provider_error(
    status_code: int | None,
    message: str,
    exc: Exception | None = None,
) -> tuple[str, str]:
    lower_message = message.lower()
    if exc is not None:
        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.ProxyError,
                httpx.RemoteProtocolError,
            ),
        ):
            return "network_error", "Cannot reach the provider. Check network, DNS, proxy, or TLS settings."
        if isinstance(exc, httpx.RequestError):
            return "network_error", "Provider request failed before a response was received."

    if status_code in {401, 403}:
        return "invalid_key", "The provider rejected the API key or permissions."
    if status_code == 404:
        return "model_not_found", "The provider could not find the requested model."
    if status_code == 429:
        return "rate_limited", "The provider rate limited the test request."
    if any(term in lower_message for term in ("quota", "balance", "insufficient")):
        return "quota_or_balance", "The provider reports a quota or balance problem."
    if status_code is not None and status_code >= 500:
        return "provider_error", "The provider returned a server error."
    return "unknown", "The provider test failed, but the error could not be classified."


def _provider_base_url(provider_config: dict[str, Any]) -> str:
    base_url = str(
        provider_config.get("base_url")
        or provider_config.get("detect_url")
        or ""
    ).strip()
    return base_url.rstrip("/")


async def _test_openai_compatible(
    provider_config: dict[str, Any],
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    provider_id = str(provider_config["id"])
    base_url = _provider_base_url(provider_config)
    if not base_url:
        return {
            "ok": False,
            "provider": provider_id,
            "error_code": "provider_error",
            "message": "Provider registry is missing a base URL.",
        }

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
    except Exception as exc:  # noqa: BLE001 - mapped to user-facing provider errors
        error_code, message = classify_provider_error(None, redact_text(exc), exc)
        return {
            "ok": False,
            "provider": provider_id,
            "error_code": error_code,
            "message": message,
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    if 200 <= response.status_code < 300:
        return {
            "ok": True,
            "provider": provider_id,
            "model": model,
            "latency_ms": latency_ms,
        }

    body = _response_body(response)
    error_code, message = classify_provider_error(response.status_code, body)
    return {
        "ok": False,
        "provider": provider_id,
        "error_code": error_code,
        "message": message,
    }


async def _test_ollama(
    provider_config: dict[str, Any],
    model: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    provider_id = str(provider_config["id"])
    base_url = _provider_base_url(provider_config)
    if not base_url:
        return {
            "ok": False,
            "provider": provider_id,
            "error_code": "provider_error",
            "message": "Ollama registry entry is missing a detection URL.",
        }
    url = f"{base_url}/models"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url)
    except Exception as exc:  # noqa: BLE001 - mapped to user-facing provider errors
        error_code, message = classify_provider_error(None, redact_text(exc), exc)
        return {
            "ok": False,
            "provider": provider_id,
            "error_code": error_code,
            "message": message,
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    if 200 <= response.status_code < 300:
        return {
            "ok": True,
            "provider": provider_id,
            "model": model,
            "latency_ms": latency_ms,
        }

    body = _response_body(response)
    error_code, message = classify_provider_error(response.status_code, body)
    return {
        "ok": False,
        "provider": provider_id,
        "error_code": error_code,
        "message": message,
    }


async def test_provider_connection(
    provider_config: dict[str, Any],
    api_key: str | None,
    model: str | None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    provider_id = str(provider_config.get("id") or "").strip()
    selected_model = str(model or provider_config.get("default_model") or "").strip()
    if not provider_id:
        return {
            "ok": False,
            "provider": "",
            "error_code": "provider_error",
            "message": "Provider registry entry is missing an id.",
        }
    if not selected_model:
        return {
            "ok": False,
            "provider": provider_id,
            "error_code": "model_not_found",
            "message": "A model name is required for this provider.",
        }

    if provider_id == "ollama":
        return await _test_ollama(provider_config, selected_model, timeout_seconds)

    ok, reason = validate_key_format(provider_config, api_key)
    if not ok:
        return {
            "ok": False,
            "provider": provider_id,
            "error_code": "invalid_key",
            "message": reason,
        }

    return await _test_openai_compatible(
        provider_config,
        str(api_key or "").strip(),
        selected_model,
        timeout_seconds,
    )
