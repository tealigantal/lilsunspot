from __future__ import annotations

import json
from typing import Any

import httpx


PROVIDER_TEST_TIMEOUT_SECONDS = 8.0


ERROR_MESSAGES: dict[str, tuple[str, str, list[str]]] = {
    "invalid_key": (
        "API Key 可能不正确",
        "这个 Key 没有通过模型服务验证。请重新复制完整 Key。",
        ["重新粘贴", "打开官网获取新的 Key", "查看技术详情"],
    ),
    "network_error": (
        "暂时连不上模型服务",
        "请检查网络，稍后重试，或换一个模型服务。",
        ["重新测试", "换一个模型服务", "查看技术详情"],
    ),
    "model_not_found": (
        "这个模型暂时不可用",
        "请先选择推荐模型，或检查模型名称是否填写完整。",
        ["选择推荐模型", "查看技术详情"],
    ),
    "rate_limited": (
        "请求太频繁或额度不足",
        "请等一会儿重试，或打开模型服务官网检查账户额度。",
        ["稍后重试", "检查账户额度", "查看技术详情"],
    ),
    "quota_exceeded": (
        "账户额度可能不足",
        "请打开模型服务官网查看余额或充值状态。",
        ["打开官网查看余额", "换一个模型服务", "查看技术详情"],
    ),
    "config_write_failed": (
        "保存设置失败",
        "请点击一键修复，或打开诊断页查看问题。",
        ["一键修复", "查看诊断", "查看技术详情"],
    ),
    "unknown": (
        "连接测试没有成功",
        "请检查模型服务、API Key 和模型名称是否填写完整。",
        ["重新测试", "查看技术详情"],
    ),
}


class ProviderValidationError(ValueError):
    pass


def mask_secret(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    prefix = value[:3] if len(value) > 8 else ""
    return f"{prefix}****{value[-4:]}"


def _error_result(
    error_code: str,
    provider: str,
    model: str,
    *,
    api_key: str = "",
    http_status: int | None = None,
) -> dict[str, Any]:
    title, message, actions = ERROR_MESSAGES.get(error_code, ERROR_MESSAGES["unknown"])
    if error_code == "invalid_key" and not api_key.strip():
        message = "请粘贴模型服务提供的完整 API Key。"
    return {
        "ok": False,
        "provider": provider,
        "model": model,
        "error_code": error_code,
        "title": title,
        "message": message,
        "actions": actions,
        "suggestion": actions[0],
        "safe_details": {
            "provider": provider,
            "masked_key": mask_secret(api_key),
            "http_status": http_status,
        },
    }


def _provider_base_url(provider_config: dict[str, Any]) -> str:
    base_url = str(provider_config.get("base_url") or provider_config.get("detect_url") or "").strip()
    if not base_url:
        raise ProviderValidationError("Provider 缺少检测地址。")
    return base_url.rstrip("/") + "/"


def _make_http_client(base_url: str) -> httpx.AsyncClient:
    timeout = httpx.Timeout(PROVIDER_TEST_TIMEOUT_SECONDS, connect=5.0)
    return httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=False)


def _request_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "lilsunspotd-provider-check",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _error_text(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False).lower()
    except (TypeError, ValueError):
        return ""


def _classify_http_error(status_code: int, payload: Any) -> str:
    text = _error_text(payload)
    if (
        status_code in {401, 403}
        or "unauthorized" in text
        or "invalid api key" in text
        or "invalid_api_key" in text
        or "incorrect api key" in text
    ):
        return "invalid_key"
    if status_code == 429 or "rate limit" in text or "rate_limited" in text:
        return "rate_limited"
    if status_code == 402 or "quota" in text or "insufficient" in text:
        return "quota_exceeded"
    if status_code == 404 or ("model" in text and "not" in text):
        return "model_not_found"
    if 500 <= status_code <= 599:
        return "network_error"
    return "unknown"


def _validation_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
        "stream": False,
    }


def _response_proves_chat_completion(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    choices = payload.get("choices")
    return isinstance(choices, list) and len(choices) > 0


async def test_provider_connection(
    provider_config: dict[str, Any],
    model: str | None,
    api_key: str,
) -> dict[str, Any]:
    """Validate an OpenAI-compatible provider with a minimal chat request."""
    provider_id = str(provider_config.get("id") or "").strip()
    provider_type = str(provider_config.get("type") or "cloud").strip().lower()
    selected_model = (model or provider_config.get("default_model") or "").strip()
    api_key = api_key.strip()

    if not provider_id:
        return _error_result("unknown", "", selected_model, api_key=api_key)
    if not selected_model:
        return _error_result("model_not_found", provider_id, "", api_key=api_key)
    if provider_type != "local" and not api_key:
        return _error_result("invalid_key", provider_id, selected_model, api_key=api_key)

    try:
        base_url = _provider_base_url(provider_config)
    except ProviderValidationError:
        return _error_result("unknown", provider_id, selected_model, api_key=api_key)

    try:
        async with _make_http_client(base_url) as client:
            response = await client.post(
                "chat/completions",
                headers=_request_headers(api_key),
                json=_validation_payload(selected_model),
            )
    except (httpx.InvalidURL, httpx.RequestError):
        return _error_result("network_error", provider_id, selected_model, api_key=api_key)

    payload = _safe_json(response)
    if response.status_code >= 400:
        error_code = _classify_http_error(response.status_code, payload)
        return _error_result(
            error_code,
            provider_id,
            selected_model,
            api_key=api_key,
            http_status=response.status_code,
        )

    if not _response_proves_chat_completion(payload):
        return _error_result(
            "unknown",
            provider_id,
            selected_model,
            api_key=api_key,
            http_status=response.status_code,
        )

    return {
        "ok": True,
        "provider": provider_id,
        "model": selected_model,
        "title": "模型服务连接通过",
        "message": "模型服务已响应，API Key 和模型名称验证通过。",
    }
