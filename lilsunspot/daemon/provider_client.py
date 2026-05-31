from __future__ import annotations

from typing import Any


ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "invalid_key": ("请先填写 API Key。", "当前骨架只检查字段是否存在，不会连接真实模型服务。"),
    "model_not_found": ("模型名称不能为空。", "请填写服务商默认模型或你要使用的模型名称。"),
    "unknown": ("连接测试占位失败。", "请检查服务商配置是否完整。"),
}


def _error_result(error_code: str, provider: str, model: str) -> dict[str, Any]:
    message, suggestion = ERROR_MESSAGES.get(error_code, ERROR_MESSAGES["unknown"])
    return {
        "ok": False,
        "provider": provider,
        "model": model,
        "error_code": error_code,
        "message": message,
        "suggestion": suggestion,
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
        return _error_result("unknown", "", selected_model)
    if not selected_model:
        return _error_result("model_not_found", provider_id, "")
    if provider_type != "local" and not api_key:
        return _error_result("invalid_key", provider_id, selected_model)

    return {
        "ok": True,
        "provider": provider_id,
        "model": selected_model,
        "message": "Provider 配置字段检查通过；当前骨架未发起真实服务调用。",
    }
