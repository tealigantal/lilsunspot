from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .chat_client import current_runtime_model, image_recognition_status
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .gateway import weixin_status
from .hermes_runtime import read_hermes_config
from .providers import provider_by_id


CAPABILITY_GRAPH_VERSION = 1
CAPABILITY_STATUSES = {"ready", "needs_setup", "degraded", "blocked", "unknown"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _action(action_id: str, label: str) -> dict[str, str]:
    return {"id": action_id, "label": label}


def _node(
    capability_id: str,
    *,
    label: str,
    status: str,
    source: str,
    user_message_cn: str,
    next_actions: list[dict[str, str]] | None = None,
    blocking_reason: str = "",
    last_verified_at: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = status if status in CAPABILITY_STATUSES else "unknown"
    return {
        "id": capability_id,
        "label": label,
        "status": normalized_status,
        "source": source,
        "blocking_reason": blocking_reason,
        "user_message_cn": user_message_cn,
        "next_actions": next_actions or [],
        "last_verified_at": last_verified_at,
        "details": details or {},
    }


def _auxiliary_vision_public_config(config: dict[str, Any]) -> dict[str, Any]:
    lilsunspot = config.get("lilsunspot") if isinstance(config.get("lilsunspot"), dict) else {}
    public_auxiliary = lilsunspot.get("auxiliary") if isinstance(lilsunspot.get("auxiliary"), dict) else {}
    public_vision = public_auxiliary.get("vision") if isinstance(public_auxiliary.get("vision"), dict) else {}
    auxiliary = config.get("auxiliary") if isinstance(config.get("auxiliary"), dict) else {}
    hermes_vision = auxiliary.get("vision") if isinstance(auxiliary.get("vision"), dict) else {}
    return {
        "provider": str(public_vision.get("provider") or hermes_vision.get("provider") or "").strip(),
        "model": str(public_vision.get("model") or hermes_vision.get("model") or "").strip(),
        "updated_at": str(public_vision.get("updated_at") or "").strip(),
        "hermes_provider": str(hermes_vision.get("provider") or "").strip(),
        "base_url_configured": bool(str(public_vision.get("base_url") or hermes_vision.get("base_url") or "").strip()),
    }


def _chat_text_node(runtime_model: dict[str, Any], provider_config: dict[str, Any] | None) -> dict[str, Any]:
    provider = str(runtime_model.get("provider") or "")
    model = str(runtime_model.get("model") or "")
    if not runtime_model.get("configured"):
        return _node(
            "chat.text",
            label="文字聊天",
            status="needs_setup",
            source="main_model",
            blocking_reason="setup.missing_model",
            user_message_cn="还没有设置 AI 服务，暂时不能聊天。",
            next_actions=[_action("open_model_settings", "设置 AI 服务")],
            details={"provider": "", "model": ""},
        )
    if provider_config is None:
        return _node(
            "chat.text",
            label="文字聊天",
            status="blocked",
            source="main_model",
            blocking_reason="setup.provider_unknown",
            user_message_cn="已保存的 AI 服务不在当前支持列表里，需要重新选择。",
            next_actions=[_action("open_model_settings", "重新设置模型")],
            details={"provider": provider, "model": model},
        )
    return _node(
        "chat.text",
        label="文字聊天",
        status="ready",
        source="main_model",
        user_message_cn="文字聊天已可用。",
        next_actions=[],
        details={
            "provider": provider,
            "provider_name": str(provider_config.get("display_name") or provider),
            "model": model,
            "verification_status": "configured",
        },
    )


def _image_read_node(
    runtime_model: dict[str, Any],
    provider_config: dict[str, Any] | None,
    config: dict[str, Any],
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    provider = str(runtime_model.get("provider") or "")
    model = str(runtime_model.get("model") or "")
    if not runtime_model.get("configured") or provider_config is None:
        return _node(
            "image.read",
            label="图片识别",
            status="needs_setup",
            source="none",
            blocking_reason="setup.missing_model",
            user_message_cn="还没有可用的聊天模型，图片只能先保存和预览。",
            next_actions=[_action("open_model_settings", "设置 AI 服务")],
            details={"backend": "none", "provider": provider, "model": model},
        )

    image_status = image_recognition_status(provider, model, config=config, paths=paths)
    details: dict[str, Any] = {
        "backend": str(image_status.get("backend") or "none"),
        "source": str(image_status.get("source") or "none"),
        "provider": provider,
        "provider_name": str(provider_config.get("display_name") or provider),
        "model": model,
        "main_supports_image": bool(image_status.get("main_supports_image")),
        "auxiliary_configured": bool(image_status.get("auxiliary_configured")),
        "image_input_mode": str(image_status.get("image_input_mode") or "text"),
        "verification_status": str(image_status.get("verification_status") or "unknown"),
        "last_error_code": str(image_status.get("last_error_code") or ""),
        "last_verified_at": str(image_status.get("last_verified_at") or ""),
        "resolved_provider": str(image_status.get("resolved_provider") or ""),
        "resolved_model": str(image_status.get("resolved_model") or ""),
        "available_vision_backends": list(image_status.get("available_vision_backends") or []),
    }

    if image_status.get("backend") == "main_model":
        if image_status.get("verification_status") == "failed":
            return _node(
                "image.read",
                label="图片识别",
                status="blocked",
                source="main_model",
                blocking_reason=str(image_status.get("last_error_code") or "provider_error"),
                user_message_cn="当前主聊天模型声称支持图片，但最近一次真实识别失败。",
                next_actions=[_action("open_model_settings", "检查模型设置"), _action("retry", "重新验证")],
                last_verified_at=str(image_status.get("last_verified_at") or ""),
                details=details,
            )
        return _node(
            "image.read",
            label="图片识别",
            status="ready",
            source="main_model",
            user_message_cn="当前主聊天模型可以直接识别图片。",
            next_actions=[],
            last_verified_at=str(image_status.get("last_verified_at") or ""),
            details=details,
        )

    if image_status.get("backend") == "auxiliary_vision":
        auxiliary = _auxiliary_vision_public_config(config)
        verification_status = str(image_status.get("verification_status") or "configured_not_verified")
        if verification_status == "verified":
            return _node(
                "image.read",
                label="图片识别",
                status="ready",
                source="auxiliary_vision",
                user_message_cn="图片识别模型已通过真实验证；上传图片时会先由它读图，再交给当前聊天模型回答。",
                next_actions=[_action("retry", "重新验证"), _action("open_vision_settings", "检查图片识别设置")],
                last_verified_at=str(image_status.get("last_verified_at") or ""),
                details={
                    **details,
                    "auxiliary_provider": auxiliary["provider"],
                    "auxiliary_model": auxiliary["model"],
                    "auxiliary_hermes_provider": auxiliary["hermes_provider"],
                    "auxiliary_base_url_configured": auxiliary["base_url_configured"],
                    "configured_at": auxiliary["updated_at"],
                },
            )
        if verification_status == "failed":
            return _node(
                "image.read",
                label="图片识别",
                status="blocked",
                source="auxiliary_vision",
                blocking_reason=str(image_status.get("last_error_code") or "provider_error"),
                user_message_cn="已保存图片识别模型，但当前不可用；图片只能先预览和保存。",
                next_actions=[_action("open_vision_settings", "检查图片识别设置"), _action("retry", "重新验证")],
                details={
                    **details,
                    "auxiliary_provider": auxiliary["provider"],
                    "auxiliary_model": auxiliary["model"],
                    "auxiliary_hermes_provider": auxiliary["hermes_provider"],
                    "auxiliary_base_url_configured": auxiliary["base_url_configured"],
                    "configured_at": auxiliary["updated_at"],
                },
            )
        return _node(
            "image.read",
            label="图片识别",
            status="degraded",
            source="auxiliary_vision",
            user_message_cn="已配置辅助视觉模型；上传图片时会先由它读图，再交给当前聊天模型回答。",
            next_actions=[_action("retry", "上传图片验证"), _action("open_vision_settings", "检查图片识别设置")],
            last_verified_at="",
            details={
                **details,
                "auxiliary_provider": auxiliary["provider"],
                "auxiliary_model": auxiliary["model"],
                "auxiliary_hermes_provider": auxiliary["hermes_provider"],
                "auxiliary_base_url_configured": auxiliary["base_url_configured"],
                "configured_at": auxiliary["updated_at"],
            },
        )

    return _node(
        "image.read",
        label="图片识别",
        status="needs_setup",
        source="none",
        blocking_reason="capability.unsupported",
        user_message_cn="当前模型不能直接识别图片，也还没有配置辅助视觉模型。",
        next_actions=[
            _action("open_vision_settings", "添加图片识别模型"),
            _action("continue_text_chat", "继续文字聊天"),
        ],
        details={**details, "verification_status": "not_configured"},
    )


def _file_read_node(runtime_model: dict[str, Any]) -> dict[str, Any]:
    if not runtime_model.get("configured"):
        status = "degraded"
        message = "本地文件摘要可用，但还没有聊天模型来继续分析。"
        actions = [_action("open_model_settings", "设置 AI 服务")]
    else:
        status = "ready"
        message = "常见文档和表格可先在本机生成摘要，再交给聊天模型处理。"
        actions = []
    return _node(
        "file.read",
        label="文件读取",
        status=status,
        source="local_parser",
        user_message_cn=message,
        next_actions=actions,
        details={"formats": ["pdf", "docx", "xlsx", "csv", "txt", "md"]},
    )


def _mode_adjust_node() -> dict[str, Any]:
    return _node(
        "mode.adjust",
        label="输出模式",
        status="ready",
        source="lilsunspot_mode_state",
        user_message_cn="输出模式可用，可以通过桌面按钮或自然语言调整。",
        next_actions=[],
        details={"supports_natural_language": True},
    )


def _weixin_nodes() -> list[dict[str, Any]]:
    try:
        status = weixin_status()
    except Exception:
        status = {"available": False, "connected": False, "message": "微信状态暂时不可读取。"}
    connected = bool(status.get("connected"))
    available = bool(status.get("available"))
    if connected:
        receive = _node(
            "weixin.receive",
            label="微信接收",
            status="ready",
            source="weixin_runtime",
            user_message_cn="微信私聊接收已连接。",
            details={"status": str(status.get("status") or "")},
        )
        send = _node(
            "weixin.send_file",
            label="微信发送文件",
            status="degraded",
            source="weixin_runtime+safety.approval",
            user_message_cn="微信文件发送可创建审批，通过确认后才会发送。",
            next_actions=[_action("retry", "创建发送审批")],
            details={"requires_approval": True, "status": str(status.get("status") or "")},
        )
        return [receive, send]
    if available:
        message = str(status.get("message") or "微信还没有连接。")
        return [
            _node(
                "weixin.receive",
                label="微信接收",
                status="needs_setup",
                source="weixin_runtime",
                blocking_reason="weixin.disconnected",
                user_message_cn=message,
                next_actions=[_action("retry", "连接微信")],
                details={"status": str(status.get("status") or "")},
            ),
            _node(
                "weixin.send_file",
                label="微信发送文件",
                status="needs_setup",
                source="weixin_runtime+safety.approval",
                blocking_reason="weixin.disconnected",
                user_message_cn="连接微信后才能创建文件发送审批。",
                next_actions=[_action("retry", "连接微信")],
                details={"requires_approval": True, "status": str(status.get("status") or "")},
            ),
        ]
    return [
        _node(
            "weixin.receive",
            label="微信接收",
            status="blocked",
            source="weixin_runtime",
            blocking_reason="weixin.unavailable",
            user_message_cn=str(status.get("message") or "当前环境不可用微信能力。"),
            details={"status": str(status.get("status") or "")},
        ),
        _node(
            "weixin.send_file",
            label="微信发送文件",
            status="blocked",
            source="weixin_runtime+safety.approval",
            blocking_reason="weixin.unavailable",
            user_message_cn="当前环境不可用微信发送能力。",
            details={"requires_approval": True, "status": str(status.get("status") or "")},
        ),
    ]


def build_capability_graph(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    runtime_model = current_runtime_model(runtime_paths)
    provider_id = str(runtime_model.get("provider") or "")
    provider_config = provider_by_id(provider_id) if provider_id else None
    config = read_hermes_config(runtime_paths)
    nodes = [
        _chat_text_node(runtime_model, provider_config),
        _image_read_node(runtime_model, provider_config, config, runtime_paths),
        _file_read_node(runtime_model),
        _mode_adjust_node(),
        *_weixin_nodes(),
    ]
    return {
        "version": CAPABILITY_GRAPH_VERSION,
        "generated_at": _now_iso(),
        "nodes": nodes,
        "by_id": {node["id"]: node for node in nodes},
    }


def graph_node(graph: dict[str, Any], capability_id: str) -> dict[str, Any] | None:
    by_id = graph.get("by_id") if isinstance(graph.get("by_id"), dict) else {}
    node = by_id.get(capability_id)
    return node if isinstance(node, dict) else None
