from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import yaml

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .providers import provider_by_id


RUNTIME_CHAT_TIMEOUT_SECONDS = 45.0

CHAT_ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "empty_message": ("请先输入消息。", "输入内容后再发送。"),
    "setup_required": ("请先完成首启向导。", "打开 Provider 页，保存一个模型服务商配置。"),
    "provider_required": ("请先完成模型配置。", "在 Provider 页选择服务商和模型后保存。"),
    "missing_api_key": ("请先填写 API Key。", "重新配置模型并保存 API Key。本地模型可留空。"),
    "runtime_auth_failed": ("模型服务鉴权没有通过。", "请回到 Provider 页重新保存 API Key。"),
    "rate_limited": ("模型服务暂时限制了请求。", "请稍后重试，或打开模型服务官网检查额度。"),
    "model_unavailable": ("这个模型暂时不可用。", "请回到 Provider 页检查模型名称，或换一个推荐模型。"),
    "runtime_unavailable": ("模型服务暂时没有响应。", "请检查网络或本地模型服务，稍后再试。"),
    "runtime_response_invalid": ("模型服务返回内容不完整。", "请重新发送，或回到 Provider 页检查模型名称。"),
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


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _provider_base_url(config: dict[str, Any], provider_config: dict[str, Any]) -> str:
    model_config = config.get("model") if isinstance(config.get("model"), dict) else {}
    base_url = str(
        model_config.get("base_url")
        or provider_config.get("base_url")
        or provider_config.get("detect_url")
        or ""
    ).strip()
    return base_url.rstrip("/") + "/" if base_url else ""


def _make_http_client(base_url: str) -> httpx.AsyncClient:
    timeout = httpx.Timeout(RUNTIME_CHAT_TIMEOUT_SECONDS, connect=10.0)
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=False)


def _request_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "lilsunspotd-chat",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _chat_payload(model: str, message: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 1024,
        "stream": False,
    }


def _classify_chat_http_error(status_code: int) -> str:
    if status_code in {401, 403}:
        return "runtime_auth_failed"
    if status_code == 429:
        return "rate_limited"
    if status_code == 404:
        return "model_unavailable"
    if 500 <= status_code <= 599:
        return "runtime_unavailable"
    return "runtime_response_invalid"


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _extract_reply(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        return _extract_text_content(message.get("content"))
    return _extract_text_content(first.get("text"))


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

    base_url = _provider_base_url(config, provider_config)
    if not base_url:
        return _chat_error("provider_required"), None

    env_key = str(provider_config.get("env_key") or "").strip()
    provider_type = str(provider_config.get("type") or "cloud").strip().lower()
    api_key = _read_env(paths.hermes_home / ".env").get(env_key, "").strip() if env_key else ""
    if not api_key and provider_type != "local":
        return _chat_error("missing_api_key"), None

    return None, {
        "provider": str(provider_config["id"]),
        "model": model,
        "provider_type": provider_type,
        "base_url": base_url,
        "api_key": api_key,
    }


async def send_chat_message(
    message: str,
    conversation_id: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    del conversation_id
    message = message.strip()
    if not message:
        return _chat_error("empty_message")
    paths = paths or ensure_runtime_dirs()
    error, settings = _load_chat_settings(paths)
    if error is not None:
        return error
    assert settings is not None

    try:
        async with _make_http_client(settings["base_url"]) as client:
            response = await client.post(
                "chat/completions",
                headers=_request_headers(settings["api_key"]),
                json=_chat_payload(settings["model"], message),
            )
    except (httpx.InvalidURL, httpx.RequestError):
        return _chat_error("runtime_unavailable")

    payload = _safe_json(response)
    if response.status_code >= 400:
        return _chat_error(_classify_chat_http_error(response.status_code))

    reply = _extract_reply(payload)
    if not reply:
        return _chat_error("runtime_response_invalid")

    return {
        "ok": True,
        "reply": reply,
        "engine": "hermes_runtime_adapter",
        "provider": settings["provider"],
        "model": settings["model"],
    }
