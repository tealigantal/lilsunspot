from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import yaml

from . import provider_client as provider_http
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .modes import get_current_mode
from .providers import provider_by_id


CHAT_TIMEOUT_SECONDS = 45.0
VISION_SUMMARY_PROMPT = (
    "请用中文简要识别这张图片。只描述你确实看见的内容，"
    "不要推测身份、隐私信息或图片外的背景。"
)

CHAT_ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "empty_message": ("请先输入要发送的内容。", "输入一句话后再发送。"),
    "setup_required": ("还不能聊天：还没有设置 AI 服务。", "请先完成首启设置，测试并保存一个 AI 服务。"),
    "provider_required": ("还不能聊天：模型服务设置不可用。", "请重新选择 AI 服务和模型后保存。"),
    "missing_api_key": ("还不能聊天：请先填写 API Key。", "重新配置模型并保存 API Key。本地模型可留空。"),
    "invalid_key": ("模型服务没有接受当前 API Key。", "请回到模型设置页，重新测试并保存 API Key。"),
    "quota_exceeded": ("模型服务额度可能不足。", "请打开模型服务官网检查余额或额度。"),
    "rate_limited": ("请求太频繁。", "请稍等一会儿再发送。"),
    "provider_error": ("模型服务商暂时没有正常响应。", "请稍后重试，或到模型设置里换一个服务。"),
    "network_error": ("暂时连不上模型服务。", "请检查网络、本地模型服务或代理设置。"),
    "model_not_found": ("当前模型名称不可用。", "请回到模型设置页，选择推荐模型后重新保存。"),
    "empty_response": ("模型服务没有返回可显示内容。", "请稍后重试，或换一个模型。"),
    "unknown": ("聊天请求没有成功。", "请稍后重试，或重新检查 AI 服务设置。"),
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


def _make_chat_http_client(base_url: str) -> httpx.AsyncClient:
    timeout = httpx.Timeout(CHAT_TIMEOUT_SECONDS, connect=8.0)
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=False)


def _chat_request_headers(api_key: str) -> dict[str, str]:
    headers = provider_http._request_headers(api_key)
    headers["User-Agent"] = "lilsunspotd-chat"
    return headers


def _chat_payload(
    model: str,
    message: str,
    system_hint: str,
    *,
    image_data_url: str | None = None,
) -> dict[str, Any]:
    messages = []
    if system_hint:
        messages.append({"role": "system", "content": system_hint})
    if image_data_url:
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        )
    else:
        messages.append({"role": "user", "content": message})
    return {
        "model": model,
        "messages": messages,
        "stream": False,
    }


def _model_supports_image_url(provider: str, model: str) -> bool:
    provider_value = provider.strip().lower()
    model_value = model.strip().lower()
    if provider_value == "deepseek":
        return False
    if provider_value == "openai":
        return any(
            token in model_value
            for token in (
                "gpt-4o",
                "gpt-4.1",
                "gpt-5",
                "o3",
                "o4",
                "vision",
            )
        )
    if provider_value == "qwen":
        return any(token in model_value for token in ("vl", "qvq", "omni", "vision"))
    if provider_value == "openrouter":
        return any(
            token in model_value
            for token in (
                "gpt-4o",
                "gpt-4.1",
                "gpt-5",
                "claude-3",
                "gemini",
                "qwen-vl",
                "qwen2.5-vl",
                "vision",
            )
        )
    if provider_value == "ollama":
        return any(token in model_value for token in ("llava", "bakllava", "moondream", "minicpm-v", "qwen-vl"))
    return "vision" in model_value or "-vl" in model_value


def _image_not_supported_message(provider: str, model: str) -> str:
    if provider.strip().lower() == "deepseek":
        return f"图片已收到并可预览；当前 DeepSeek 文本模型 {model} 不能识别图片内容。"
    return (
        f"图片已收到并可预览；当前模型 {provider}/{model} 没有确认支持 image_url 视觉输入。"
        "请切换到支持图片的 OpenAI 或 Qwen-VL 模型后再试。"
    )


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
            continue
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str):
            parts.append(text)
            continue
        nested_content = part.get("content")
        if isinstance(nested_content, str):
            parts.append(nested_content)
    return "\n".join(item.strip() for item in parts if item.strip()).strip()


def _extract_reply(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return ""

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        reply = _content_to_text(message.get("content"))
        if reply:
            return reply
    return ""


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
    provider_config = dict(provider_config)
    saved_base_url = str(model_config.get("base_url") or "").strip()
    if saved_base_url:
        provider_config["base_url"] = saved_base_url

    env_key = str(provider_config.get("env_key") or "").strip()
    provider_type = str(provider_config.get("type") or "cloud").strip().lower()
    api_key = _read_env(paths.hermes_home / ".env").get(env_key, "").strip()
    if not api_key and provider_type != "local":
        return _chat_error("missing_api_key"), None

    current_mode = get_current_mode(paths)
    prompt = current_mode.get("prompt") if isinstance(current_mode.get("prompt"), dict) else {}
    system_hint = str(prompt.get("system_hint") or "").strip()

    return None, {
        "provider": str(provider_config["id"]),
        "model": model,
        "provider_type": provider_type,
        "provider_config": provider_config,
        "api_key": api_key,
        "mode": str(current_mode.get("current") or "balanced"),
        "system_hint": system_hint,
    }


async def send_chat_message(
    message: str,
    conversation_id: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    # P0 chat is a single-turn OpenAI-compatible provider adapter. The
    # conversation id is returned as unsupported instead of being silently used.
    conversation_id_requested = bool(conversation_id)
    message = message.strip()
    if not message:
        return _chat_error("empty_message")

    paths = paths or ensure_runtime_dirs()
    error, settings = _load_chat_settings(paths)
    if error is not None:
        return error
    assert settings is not None

    try:
        base_url = provider_http._provider_base_url(settings["provider_config"])
    except provider_http.ProviderValidationError:
        return _chat_error("provider_required")

    try:
        async with _make_chat_http_client(base_url) as client:
            response = await client.post(
                "chat/completions",
                headers=_chat_request_headers(settings["api_key"]),
                json=_chat_payload(settings["model"], message, settings["system_hint"]),
            )
    except (httpx.InvalidURL, httpx.RequestError):
        return _chat_error("network_error")

    payload = provider_http._safe_json(response)
    if response.status_code >= 400:
        return _chat_error(provider_http._classify_http_error(response.status_code, payload))

    reply = _extract_reply(payload)
    if not reply:
        return _chat_error("empty_response")

    return {
        "ok": True,
        "reply": reply,
        "engine": "lilsunspot_provider_adapter",
        "provider": settings["provider"],
        "model": settings["model"],
        "conversation_id": None,
        "conversation_id_supported": False,
        "conversation_id_requested": conversation_id_requested,
    }


async def describe_image_data_url(
    image_data_url: str,
    *,
    file_name: str = "图片",
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    image_data_url = image_data_url.strip()
    if not image_data_url.startswith("data:image/"):
        return {
            "ok": False,
            "error_code": "invalid_image",
            "message": "图片预览数据不可读取，暂时不能做视觉识别。",
        }

    paths = paths or ensure_runtime_dirs()
    error, settings = _load_chat_settings(paths)
    if error is not None:
        return {
            "ok": False,
            "error_code": str(error.get("error_code") or "setup_required"),
            "message": str(error.get("message") or "还不能识别图片：还没有设置 AI 服务。"),
        }
    assert settings is not None

    provider = str(settings["provider"])
    model = str(settings["model"])
    if not _model_supports_image_url(provider, model):
        return {
            "ok": False,
            "error_code": "image_not_supported",
            "message": _image_not_supported_message(provider, model),
        }

    try:
        base_url = provider_http._provider_base_url(settings["provider_config"])
    except provider_http.ProviderValidationError:
        return {
            "ok": False,
            "error_code": "provider_required",
            "message": "当前模型服务设置不可用，暂时不能识别图片。",
        }

    prompt = f"{VISION_SUMMARY_PROMPT}\n文件名：{file_name or '图片'}"
    try:
        async with _make_chat_http_client(base_url) as client:
            response = await client.post(
                "chat/completions",
                headers=_chat_request_headers(settings["api_key"]),
                json=_chat_payload(
                    model,
                    prompt,
                    settings["system_hint"],
                    image_data_url=image_data_url,
                ),
            )
    except (httpx.InvalidURL, httpx.RequestError):
        return {
            "ok": False,
            "error_code": "network_error",
            "message": "图片已收到并可预览；视觉识别暂时连不上模型服务。",
        }

    payload = provider_http._safe_json(response)
    if response.status_code >= 400:
        return {
            "ok": False,
            "error_code": provider_http._classify_http_error(response.status_code, payload),
            "message": "图片已收到并可预览；当前模型没有成功完成视觉识别。",
        }

    reply = _extract_reply(payload)
    if not reply:
        return {
            "ok": False,
            "error_code": "empty_response",
            "message": "图片已收到并可预览；当前模型没有返回可显示的识别结果。",
        }
    return {
        "ok": True,
        "summary": reply,
        "provider": provider,
        "model": model,
    }
