from __future__ import annotations

import os
import time
from datetime import datetime, timezone
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


def _record_image_verification(
    paths: RuntimePaths,
    *,
    ok: bool,
    backend: str,
    provider: str,
    model: str,
    error_code: str = "",
) -> None:
    if backend not in {"main_model", "auxiliary_vision"}:
        return
    try:
        from .hermes_runtime import read_hermes_config, write_hermes_config

        config = read_hermes_config(paths)
        lilsunspot = config.setdefault("lilsunspot", {})
        if not isinstance(lilsunspot, dict):
            return
        verification = lilsunspot.setdefault("capability_verification", {})
        if not isinstance(verification, dict):
            verification = {}
            lilsunspot["capability_verification"] = verification
        verification["image.read"] = {
            "verification_status": "verified" if ok else "failed",
            "last_error_code": "" if ok else error_code,
            "backend": backend,
            "resolved_provider": provider,
            "resolved_model": model,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        write_hermes_config(config, paths)
    except Exception:
        pass


def _image_verification_from_config(config: dict[str, Any]) -> dict[str, Any]:
    lilsunspot = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    verification = lilsunspot.get("capability_verification") if isinstance(lilsunspot.get("capability_verification"), dict) else {}
    image = verification.get("image.read") if isinstance(verification.get("image.read"), dict) else {}
    return image


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


def _cached_models_dev_data() -> dict[str, Any]:
    try:
        from agent import models_dev

        cache = getattr(models_dev, "_models_dev_cache", {})
        cache_time = float(getattr(models_dev, "_models_dev_cache_time", 0) or 0)
        cache_ttl = float(getattr(models_dev, "_MODELS_DEV_CACHE_TTL", 3600) or 3600)
        if isinstance(cache, dict) and cache and time.time() - cache_time < cache_ttl:
            return cache

        disk_age_func = getattr(models_dev, "_disk_cache_age_seconds", None)
        load_disk_cache = getattr(models_dev, "_load_disk_cache", None)
        if callable(disk_age_func) and callable(load_disk_cache):
            disk_age = disk_age_func()
            if disk_age is not None and disk_age < cache_ttl:
                disk_data = load_disk_cache()
                if isinstance(disk_data, dict):
                    return disk_data
    except Exception:
        return {}
    return {}


def _model_entry_from_cached_models_dev(provider: str, model: str) -> dict[str, Any] | None:
    try:
        from agent import models_dev

        provider_map = getattr(models_dev, "PROVIDER_TO_MODELS_DEV", {})
        models_dev_provider = provider_map.get(provider)
        if not models_dev_provider:
            return None
        data = _cached_models_dev_data()
        provider_data = data.get(models_dev_provider)
        if not isinstance(provider_data, dict):
            return None
        models = provider_data.get("models")
        if not isinstance(models, dict):
            return None
        finder = getattr(models_dev, "_find_model_entry", None)
        if callable(finder):
            entry = finder(models, model)
            return entry if isinstance(entry, dict) else None
    except Exception:
        return None
    return None


def _cached_supports_vision(provider: str, model: str) -> bool | None:
    entry = _model_entry_from_cached_models_dev(provider, model)
    if entry is None:
        return None
    modalities = entry.get("modalities")
    input_modalities = modalities.get("input") if isinstance(modalities, dict) else None
    if isinstance(input_modalities, list):
        return "image" in input_modalities
    return bool(entry.get("attachment", False))


def _model_supports_image_url(provider: str, model: str, config: dict[str, Any] | None = None) -> bool:
    try:
        from agent.image_routing import _supports_vision_override

        supports = _supports_vision_override(config if isinstance(config, dict) else {}, provider, model)
    except Exception:
        supports = None
    if supports is None:
        supports = _cached_supports_vision(provider, model)
    return supports is True


def _auxiliary_vision_configured(config: dict[str, Any]) -> bool:
    try:
        from agent.image_routing import _explicit_aux_vision_override

        return bool(_explicit_aux_vision_override(config))
    except Exception:
        return False


def _capability_provider_for_model(provider: str, config: dict[str, Any]) -> str:
    model_config = config.get("model") if isinstance(config.get("model"), dict) else {}
    config_provider = str(model_config.get("provider") or "").strip()
    provider_config = provider_by_id(provider)
    hermes_provider = str((provider_config or {}).get("hermes_provider") or config_provider or provider).strip()
    if hermes_provider and hermes_provider != "custom":
        return hermes_provider
    return config_provider or provider


def _image_input_mode_for_status(config: dict[str, Any], main_supports_image: bool) -> str:
    agent_config = config.get("agent") if isinstance(config.get("agent"), dict) else {}
    configured_mode = str(agent_config.get("image_input_mode") or "auto").strip().lower()
    if configured_mode == "native":
        return "native"
    if configured_mode == "text":
        return "text"
    if _auxiliary_vision_configured(config):
        return "text"
    return "native" if main_supports_image else "text"


def _prepare_hermes_runtime_env(paths: RuntimePaths) -> None:
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(paths.hermes_home)
    try:
        from hermes_cli.env_loader import load_hermes_dotenv

        load_hermes_dotenv(hermes_home=paths.hermes_home)
    except Exception:
        pass


def _available_vision_backends(paths: RuntimePaths | None = None) -> list[str]:
    if paths is not None:
        _prepare_hermes_runtime_env(paths)
    try:
        from agent.auxiliary_client import get_available_vision_backends

        return [str(item) for item in get_available_vision_backends() if str(item).strip()]
    except Exception:
        return []


def _resolve_hermes_vision_backend(
    paths: RuntimePaths | None = None,
    *,
    async_mode: bool = False,
) -> tuple[str | None, Any | None, str | None]:
    if paths is not None:
        _prepare_hermes_runtime_env(paths)
    try:
        from agent.auxiliary_client import resolve_vision_provider_client

        return resolve_vision_provider_client(async_mode=async_mode)
    except Exception:
        return None, None, None


def image_recognition_status(
    provider: str,
    model: str,
    *,
    config: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    config = config if isinstance(config, dict) else {}
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        return {
            "supports_image": False,
            "main_supports_image": False,
            "auxiliary_configured": False,
            "backend": "none",
            "source": "none",
            "image_input_mode": "text",
            "verification_status": "not_configured",
            "last_error_code": "",
            "last_verified_at": "",
            "resolved_provider": "",
            "resolved_model": "",
            "available_vision_backends": [],
        }
    if paths is not None:
        _prepare_hermes_runtime_env(paths)
    capability_provider = _capability_provider_for_model(provider, config)
    main_supports_image = _model_supports_image_url(capability_provider, model, config)
    auxiliary_configured = _auxiliary_vision_configured(config)
    image_input_mode = _image_input_mode_for_status(config, main_supports_image)

    available_backends = _available_vision_backends(paths) if auxiliary_configured else []
    resolved_provider = ""
    resolved_model = ""
    last_error_code = ""
    last_verified_at = ""
    if image_input_mode == "native":
        backend = "main_model"
        source = "main_model"
        supports_image = True
        verification_status = "inferred_from_model_metadata"
        resolved_provider = capability_provider
        resolved_model = model
    else:
        resolver_provider, resolver_client, resolver_model = (
            _resolve_hermes_vision_backend(paths) if auxiliary_configured else (None, None, None)
        )
        if resolver_provider:
            resolved_provider = str(resolver_provider)
        if resolver_model:
            resolved_model = str(resolver_model)
        if resolver_client is not None:
            backend = "auxiliary_vision"
            source = "auxiliary_vision"
            supports_image = True
            verification_status = "configured_not_verified"
        elif auxiliary_configured:
            backend = "auxiliary_vision"
            source = "auxiliary_vision"
            supports_image = False
            verification_status = "failed"
            last_error_code = "missing_api_key"
        else:
            backend = "none"
            source = "none"
            supports_image = False
            verification_status = "not_configured"
    verification = _image_verification_from_config(config)
    if (
        backend in {"main_model", "auxiliary_vision"}
        and str(verification.get("backend") or "") == backend
        and str(verification.get("resolved_provider") or "") == resolved_provider
        and str(verification.get("resolved_model") or "") == resolved_model
    ):
        recorded_status = str(verification.get("verification_status") or "").strip()
        if recorded_status in {"verified", "failed"}:
            verification_status = recorded_status
            last_error_code = str(verification.get("last_error_code") or "").strip()
            last_verified_at = str(verification.get("updated_at") or "").strip()
            supports_image = recorded_status == "verified"
    return {
        "supports_image": bool(supports_image),
        "main_supports_image": bool(main_supports_image),
        "auxiliary_configured": bool(auxiliary_configured),
        "backend": backend,
        "source": source,
        "image_input_mode": image_input_mode,
        "verification_status": verification_status,
        "last_error_code": last_error_code,
        "last_verified_at": last_verified_at,
        "resolved_provider": resolved_provider,
        "resolved_model": resolved_model,
        "available_vision_backends": available_backends,
    }


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
    image_status = image_recognition_status(provider_id, model, config=config, paths=paths)

    return None, {
        "provider": str(provider_config["id"]),
        "model": model,
        "provider_type": provider_type,
        "provider_config": provider_config,
        "api_key": api_key,
        "mode": str(current_mode.get("current") or "balanced"),
        "system_hint": system_hint,
        "image_supports_native": image_status["backend"] == "main_model",
        "image_backend": image_status["backend"],
        "config": config,
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


def _vision_error_message(error_code: str, backend: str) -> str:
    model_label = "图片识别模型" if backend == "auxiliary_vision" else "当前模型"
    if error_code == "invalid_key":
        return f"图片已收到并可预览；{model_label}没有接受当前 API Key。"
    if error_code == "missing_api_key":
        return f"图片已收到并可预览；{model_label}还缺 API Key。"
    if error_code == "model_not_found":
        return f"图片已收到并可预览；{model_label}名称不可用。"
    if error_code in {"quota_exceeded", "quota_exhausted"}:
        return f"图片已收到并可预览；{model_label}账户额度可能不足。"
    if error_code == "rate_limited":
        return f"图片已收到并可预览；{model_label}请求太频繁，请稍后再试。"
    if error_code == "network_error":
        return f"图片已收到并可预览；暂时连不上{model_label}。"
    if error_code == "provider_error":
        return f"图片已收到并可预览；{model_label}暂时没有正常响应。"
    return f"图片已收到并可预览；{model_label}没有成功完成视觉识别。"


def _classify_vision_exception(exc: Exception) -> str:
    text = str(exc).lower()
    status_code = str(getattr(exc, "status_code", "") or "")
    if "api key" in text or "unauthorized" in text or "invalid key" in text or status_code in {"401", "403"}:
        return "invalid_key"
    if "not found" in text or "model_not_found" in text or status_code == "404":
        return "model_not_found"
    if "rate" in text or "too many requests" in text or status_code == "429":
        return "rate_limited"
    if "quota" in text or "credit" in text or "insufficient" in text or status_code == "402":
        return "quota_exhausted"
    if "timeout" in text or "network" in text or "connection" in text or "connect" in text:
        return "network_error"
    if status_code:
        return "provider_error"
    return "unknown"


def _value_from_obj(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return getattr(payload, key, None)


def _extract_llm_response_text(payload: Any) -> str:
    output_text = _value_from_obj(payload, "output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    choices = _value_from_obj(payload, "choices")
    if isinstance(choices, list):
        for choice in choices:
            message = _value_from_obj(choice, "message")
            if message is None:
                continue
            reply = _content_to_text(_value_from_obj(message, "content"))
            if reply:
                return reply

    message = _value_from_obj(payload, "message")
    if message is not None:
        reply = _content_to_text(_value_from_obj(message, "content"))
        if reply:
            return reply

    return _content_to_text(_value_from_obj(payload, "content"))


async def _call_hermes_vision(messages: list[dict[str, Any]]) -> Any:
    provider, client, model = _resolve_hermes_vision_backend(async_mode=True)
    if client is None or not model:
        raise RuntimeError("no hermes vision backend")

    request: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    try:
        from agent.auxiliary_client import auxiliary_max_tokens_param, get_auxiliary_extra_body

        request.update(auxiliary_max_tokens_param(300))
        extra_body = get_auxiliary_extra_body()
        if extra_body:
            request["extra_body"] = extra_body
    except Exception:
        request["max_tokens"] = 300

    return await client.chat.completions.create(**request)


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
            "stage": "vision.input",
            "backend": "none",
            "message": "图片预览数据不可读取，暂时不能做视觉识别。",
        }

    paths = paths or ensure_runtime_dirs()
    error, settings = _load_chat_settings(paths)
    if error is not None:
        return {
            "ok": False,
            "error_code": str(error.get("error_code") or "setup_required"),
            "stage": str(error.get("stage") or "setup.model"),
            "backend": "none",
            "message": str(error.get("message") or "还不能识别图片：还没有设置 AI 服务。"),
        }
    assert settings is not None

    provider = str(settings["provider"])
    model = str(settings["model"])
    image_status = image_recognition_status(provider, model, config=settings["config"], paths=paths)
    backend = str(image_status.get("backend") or "none")
    stage = "vision.native" if backend == "main_model" else "vision.auxiliary"
    resolved_provider = str(image_status.get("resolved_provider") or provider)
    resolved_model = str(image_status.get("resolved_model") or model)
    if backend == "none":
        return {
            "ok": False,
            "error_code": "image_not_supported",
            "stage": "capability.unsupported",
            "backend": "none",
            "provider": provider,
            "model": model,
            "message": _image_not_supported_message(provider, model),
        }
    if image_status.get("verification_status") == "failed":
        error_code = str(image_status.get("last_error_code") or "unknown")
        return {
            "ok": False,
            "error_code": error_code,
            "stage": stage,
            "backend": backend,
            "provider": resolved_provider,
            "model": resolved_model,
            "message": _vision_error_message(error_code, backend),
        }

    prompt = f"{VISION_SUMMARY_PROMPT}\n文件名：{file_name or '图片'}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]
    try:
        _prepare_hermes_runtime_env(paths)
        response = await _call_hermes_vision(messages)
    except Exception as exc:
        error_code = _classify_vision_exception(exc)
        _record_image_verification(
            paths,
            ok=False,
            backend=backend,
            provider=resolved_provider,
            model=resolved_model,
            error_code=error_code,
        )
        return {
            "ok": False,
            "error_code": error_code,
            "stage": stage,
            "backend": backend,
            "provider": resolved_provider,
            "model": resolved_model,
            "message": _vision_error_message(error_code, backend),
        }

    reply = _extract_llm_response_text(response)
    if not reply:
        _record_image_verification(
            paths,
            ok=False,
            backend=backend,
            provider=resolved_provider,
            model=resolved_model,
            error_code="empty_response",
        )
        return {
            "ok": False,
            "error_code": "empty_response",
            "stage": stage,
            "backend": backend,
            "provider": resolved_provider,
            "model": resolved_model,
            "message": "图片已收到并可预览；模型没有返回可显示的识别结果。",
        }
    _record_image_verification(
        paths,
        ok=True,
        backend=backend,
        provider=resolved_provider,
        model=resolved_model,
    )
    return {
        "ok": True,
        "summary": reply,
        "provider": resolved_provider,
        "model": resolved_model,
        "backend": backend,
        "stage": stage,
    }
