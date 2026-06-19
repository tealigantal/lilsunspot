from __future__ import annotations

import json
from typing import Any

from .config_paths import ensure_runtime_dirs
from .mode_intents import MODE_LABELS, mode_status_message
from .modes import CUSTOM_MODE_ID, DEFAULT_MODE_ID, get_current_mode, select_mode


LILSUNSPOT_MODE_TOOLSET = "lilsunspot_mode"
GET_MODE_TOOL = "lilsunspot_get_mode"
SET_MODE_TOOL = "lilsunspot_set_mode"
MODE_IDS = ("pragmatic", "balanced", "emotional", "custom")
MODE_TOOL_SCOPES = ("global", "conversation", "turn")


GET_MODE_SCHEMA = {
    "name": GET_MODE_TOOL,
    "description": (
        "Read the current lilsunspot answer Mode for this active conversation. "
        "Do not provide a conversation id; lilsunspot takes the current conversation "
        "from the active turn context."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


SET_MODE_SCHEMA = {
    "name": SET_MODE_TOOL,
    "description": (
        "Set the lilsunspot answer Mode for the active turn context. Use this when "
        "the user asks for a different response style in normal chat. Do not pass "
        "conversation_id, chat_id, user_id, or any target; lilsunspot selects the "
        "current conversation from the turn context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": list(MODE_IDS),
                "description": "Preset mode id. Use custom when setting individual sliders.",
            },
            "style_axis": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "0 is pragmatic/direct, 100 is warm/emotional.",
            },
            "detail_level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "0 is concise, 100 is detailed.",
            },
            "autonomy_level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "0 confirms more often, 100 proceeds more proactively.",
            },
            "scope": {
                "type": "string",
                "enum": list(MODE_TOOL_SCOPES),
                "description": "conversation is the normal choice; turn applies only to the current turn; global changes the default mode.",
            },
        },
        "additionalProperties": False,
    },
}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _error(error_code: str, message: str) -> str:
    return _json({"ok": False, "error_code": error_code, "message": message})


def _current_conversation_id() -> str:
    from gateway.session_context import get_session_env

    return get_session_env("HERMES_SESSION_CHAT_ID", "").strip()


def _public_mode(mode: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    current = str(mode.get("current") or DEFAULT_MODE_ID)
    profile = mode.get("profile") if isinstance(mode.get("profile"), dict) else {}
    return {
        "current": current,
        "label": MODE_LABELS.get(current, current),
        "scope": mode.get("scope") or "",
        "conversation_id": conversation_id,
        "style_axis": int(profile.get("style_axis") or 0),
        "detail_level": int(profile.get("detail_level") or 0),
        "autonomy_level": int(profile.get("autonomy_level") or 0),
        "message": mode_status_message(mode),
    }


def _coerce_slider(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    try:
        value = int(payload.get(key))
    except (TypeError, ValueError):
        raise ValueError(f"{key} 必须是 0 到 100 的整数。")
    return max(0, min(100, value))


def _reject_target_args(payload: dict[str, Any]) -> str | None:
    forbidden = sorted({"conversation_id", "chat_id", "target", "target_id", "user_id"} & set(payload))
    if not forbidden:
        return None
    return "Mode 工具不能指定目标会话。"


def get_mode_handler(args: dict[str, Any] | None, **_kwargs: Any) -> str:
    payload = args or {}
    target_error = _reject_target_args(payload)
    if target_error:
        return _error("target_not_allowed", target_error)
    conversation_id = _current_conversation_id()
    if not conversation_id:
        return _error("no_active_conversation", "当前没有可用的对话上下文。")
    mode = get_current_mode(ensure_runtime_dirs(), conversation_id=conversation_id)
    return _json({"ok": True, "mode": _public_mode(mode, conversation_id)})


def set_mode_handler(args: dict[str, Any] | None, **_kwargs: Any) -> str:
    payload = args or {}
    target_error = _reject_target_args(payload)
    if target_error:
        return _error("target_not_allowed", target_error)

    conversation_id = _current_conversation_id()
    if not conversation_id:
        return _error("no_active_conversation", "当前没有可用的对话上下文。")

    scope = str(payload.get("scope") or "conversation").strip().lower()
    if scope not in MODE_TOOL_SCOPES:
        return _error("invalid_scope", "输出模式作用域不正确。")

    paths = ensure_runtime_dirs()
    current = get_current_mode(paths, conversation_id=conversation_id)
    requested_mode = str(payload.get("mode") or current.get("current") or DEFAULT_MODE_ID).strip().lower()
    if requested_mode not in MODE_IDS:
        return _error("invalid_mode", "没有找到这个输出模式。")

    slider_keys = ("style_axis", "detail_level", "autonomy_level")
    try:
        sliders = {key: _coerce_slider(payload, key) for key in slider_keys}
    except ValueError as exc:
        return _error("invalid_slider", str(exc))
    supplied_sliders = {key: value for key, value in sliders.items() if value is not None}
    if not payload.get("mode") and supplied_sliders:
        requested_mode = CUSTOM_MODE_ID
    if not payload.get("mode") and not supplied_sliders:
        return _error("empty_request", "请提供要设置的模式或滑杆。")

    try:
        updated = select_mode(
            requested_mode,
            paths,
            style_axis=supplied_sliders.get("style_axis"),
            detail_level=supplied_sliders.get("detail_level"),
            autonomy_level=supplied_sliders.get("autonomy_level"),
            conversation_id=conversation_id,
            scope=scope,
        )
    except ValueError as exc:
        return _error("mode_update_failed", str(exc))

    return _json(
        {
            "ok": True,
            "changed": True,
            "mode": _public_mode(updated, conversation_id),
            "message": mode_status_message(updated),
        }
    )


def register_mode_tools() -> None:
    from tools.registry import registry

    definitions = [
        (
            GET_MODE_TOOL,
            GET_MODE_SCHEMA,
            get_mode_handler,
            "Read the current lilsunspot Mode for the active conversation.",
        ),
        (
            SET_MODE_TOOL,
            SET_MODE_SCHEMA,
            set_mode_handler,
            "Set the lilsunspot Mode for the active conversation or current turn.",
        ),
    ]
    for name, schema, handler, description in definitions:
        if registry.get_entry(name) is not None:
            continue
        registry.register(
            name=name,
            toolset=LILSUNSPOT_MODE_TOOLSET,
            schema=schema,
            handler=handler,
            check_fn=lambda: True,
            description=description,
        )
