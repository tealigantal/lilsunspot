from __future__ import annotations

from typing import Any


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


async def test_provider_connection(
    provider_config: dict[str, Any],
    model: str | None,
    api_key: str,
) -> dict[str, Any]:
    """Validate provider fields without calling a real provider."""
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

    return {
        "ok": True,
        "provider": provider_id,
        "model": selected_model,
        "title": "模型服务连接通过",
        "message": "Provider 配置字段检查通过；当前骨架未发起真实服务调用。",
    }
