from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any

from . import conversations
from . import provider_client as provider_http
from .capabilities import capability_prompt_snapshot, enabled_toolsets_for_agent, fallback_chain_for_agent
from .chat_client import CHAT_ERROR_MESSAGES, _chat_error, _load_chat_settings
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .delivery_actions import delivery_turn_context
from .delivery_tools import LILSUNSPOT_DELIVERY_TOOLSET, register_delivery_tools


logger = logging.getLogger(__name__)
AGENT_ENGINE = "hermes_agent_loop"
_IMPORT_LOCK = threading.Lock()


def _ensure_hermes_home(paths: RuntimePaths) -> None:
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(paths.hermes_home)


def _load_hermes_classes(paths: RuntimePaths):
    _ensure_hermes_home(paths)
    with _IMPORT_LOCK:
        from hermes_cli.env_loader import load_hermes_dotenv

        load_hermes_dotenv(hermes_home=paths.hermes_home, project_env=Path(__file__).resolve().parents[2] / ".env")
        from hermes_state import SessionDB
        from run_agent import AIAgent

    return AIAgent, SessionDB


def _agent_error(error_code: str) -> dict[str, Any]:
    if error_code in CHAT_ERROR_MESSAGES:
        return _chat_error(error_code)
    return _chat_error("unknown")


def _settings_for_agent(paths: RuntimePaths) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    error, settings = _load_chat_settings(paths)
    if error is not None:
        return error, None
    assert settings is not None
    try:
        base_url = provider_http._provider_base_url(settings["provider_config"])
    except provider_http.ProviderValidationError:
        return _agent_error("provider_required"), None
    provider_config = settings["provider_config"]
    hermes_provider = str(provider_config.get("hermes_provider") or settings["provider"]).strip() or "custom"
    capability_hint = capability_prompt_snapshot(paths)
    system_hint = "\n\n".join(
        part
        for part in (
            str(settings.get("system_hint") or "").strip(),
            capability_hint,
        )
        if part
    )
    settings = {**settings, "system_hint": system_hint}
    return None, {**settings, "base_url": base_url, "hermes_provider": hermes_provider}


def _history_from_hermes(session_db: Any, session_id: str) -> list[dict[str, Any]]:
    try:
        history = session_db.get_messages_as_conversation(session_id, include_ancestors=True)
    except Exception as exc:
        logger.warning("Hermes session history read failed session=%s error=%s", session_id, type(exc).__name__)
        return []
    return history if isinstance(history, list) else []


def _fallback_history_from_lilsunspot(
    conversation_id: str,
    *,
    current_message_id: str | None,
    exclude_message_ids: list[str] | None = None,
    paths: RuntimePaths,
) -> list[dict[str, str]]:
    return conversations.conversation_history_for_agent(
        conversation_id,
        exclude_message_id=current_message_id,
        exclude_message_ids=exclude_message_ids,
        paths=paths,
    )


def _enabled_toolsets_for_lilsunspot_agent(paths: RuntimePaths) -> list[str]:
    register_delivery_tools()
    toolsets = list(enabled_toolsets_for_agent(paths))
    if LILSUNSPOT_DELIVERY_TOOLSET not in toolsets:
        toolsets.append(LILSUNSPOT_DELIVERY_TOOLSET)
    return toolsets


def _approval_notify_callback(session_id: str):
    def notify(approval_data: dict[str, Any]) -> None:
        try:
            from .safety import request_safety_approval

            command = str(approval_data.get("command") or "").strip()
            description = str(approval_data.get("description") or "").strip()
            summary = description or (f"Hermes 请求执行高风险操作：{command[:80]}" if command else "Hermes 请求执行高风险操作")
            request_safety_approval(
                "hermes_tool_approval",
                summary,
                {
                    "session_key": session_id,
                    "command": command,
                    "description": description,
                    "pattern_keys": approval_data.get("pattern_keys") or [],
                },
                "hermes_agent_loop",
            )
        except Exception as exc:
            logger.warning("Hermes tool approval bridge failed session=%s error=%s", session_id, type(exc).__name__)

    return notify


def _extract_reply(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    response = result.get("final_response")
    if isinstance(response, str) and response.strip():
        return response.strip()
    messages = result.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def _run_agent_turn(
    *,
    message: str,
    conversation_id: str,
    current_message_id: str | None,
    exclude_message_ids: list[str] | None,
    route: dict[str, str] | None,
    paths: RuntimePaths,
    settings: dict[str, Any],
    require_existing_conversation: bool = False,
) -> dict[str, Any]:
    AIAgent, SessionDB = _load_hermes_classes(paths)
    conversation = conversations.get_conversation(conversation_id, paths)
    if conversation is None:
        if require_existing_conversation:
            return {
                "ok": False,
                "error_code": "conversation_deleted",
                "message": "这个对话已删除，本次回复已取消。",
                "suggestion": "需要时请重新开始对话。",
                "cancelled": True,
            }
        conversation = conversations.ensure_conversation(
            conversation_id,
            paths=paths,
        )
    session_id = conversations.hermes_session_id(conversation, conversation_id)
    session_db = SessionDB()
    history = _history_from_hermes(session_db, session_id)
    if not history:
        history = _fallback_history_from_lilsunspot(
            conversation_id,
            current_message_id=current_message_id,
            exclude_message_ids=exclude_message_ids,
            paths=paths,
        )

    from gateway.session_context import clear_session_vars, set_session_vars
    from tools.approval import register_gateway_notify, reset_current_session_key, set_current_session_key, unregister_gateway_notify

    platform_name = "weixin" if route else "lilsunspot"
    tokens = set_session_vars(
        platform=platform_name,
        chat_id=conversation_id,
        chat_name=str(conversation.get("title") or ""),
        user_id=str((route or {}).get("user_id") or ""),
        session_key=session_id,
        message_id=current_message_id or "",
    )
    approval_token = set_current_session_key(session_id)
    register_gateway_notify(session_id, _approval_notify_callback(session_id))
    try:
        with delivery_turn_context(
            conversation_id=conversation_id,
            source=platform_name,
            route=route,
            paths=paths,
        ) as delivery_context:
            agent = AIAgent(
                model=settings["model"],
                provider=settings["hermes_provider"],
                base_url=settings["base_url"],
                api_key=settings["api_key"],
                enabled_toolsets=_enabled_toolsets_for_lilsunspot_agent(paths),
                fallback_model=fallback_chain_for_agent(paths),
                quiet_mode=True,
                verbose_logging=False,
                session_id=session_id,
                session_db=session_db,
                platform=platform_name,
                user_id=str((route or {}).get("user_id") or ""),
                chat_id=conversation_id,
                chat_name=str(conversation.get("title") or ""),
                chat_type=str((route or {}).get("chat_type") or ""),
                gateway_session_key=session_id,
                skip_context_files=True,
                skip_memory=False,
                ephemeral_system_prompt=str(settings.get("system_hint") or ""),
            )
            result = agent.run_conversation(
                user_message=message,
                conversation_history=history,
                task_id=session_id,
            )
            delivery_actions = delivery_context.actions_for_result()
    finally:
        unregister_gateway_notify(session_id)
        reset_current_session_key(approval_token)
        clear_session_vars(tokens)

    reply = _extract_reply(result)
    if not reply:
        return _agent_error("empty_response")
    return {
        "ok": True,
        "reply": reply,
        "engine": AGENT_ENGINE,
        "provider": str((result or {}).get("provider") or settings["provider"]),
        "model": str((result or {}).get("model") or settings["model"]),
        "conversation_id": conversation_id,
        "conversation_id_supported": True,
        "conversation_id_requested": True,
        "hermes_session_id": session_id,
        "api_calls": int((result or {}).get("api_calls") or 0),
        "messages": (result or {}).get("messages") if isinstance(result, dict) else [],
        "delivery_actions": delivery_actions,
    }


async def send_agent_message(
    message: str,
    conversation_id: str | None = None,
    paths: RuntimePaths | None = None,
    *,
    current_message_id: str | None = None,
    exclude_message_ids: list[str] | None = None,
    route: dict[str, str] | None = None,
    require_existing_conversation: bool = False,
) -> dict[str, Any]:
    conversation_id = (conversation_id or conversations.PERSONAL_CONVERSATION_ID).strip() or conversations.PERSONAL_CONVERSATION_ID
    message = message.strip()
    if not message:
        return _agent_error("empty_message")
    runtime_paths = paths or ensure_runtime_dirs()
    error, settings = _settings_for_agent(runtime_paths)
    if error is not None:
        return error
    assert settings is not None
    try:
        return await asyncio.to_thread(
            _run_agent_turn,
            message=message,
            conversation_id=conversation_id,
            current_message_id=current_message_id,
            exclude_message_ids=exclude_message_ids,
            route=route,
            paths=runtime_paths,
            settings=settings,
            require_existing_conversation=require_existing_conversation,
        )
    except Exception as exc:
        logger.exception("Hermes agent loop failed conversation=%s error=%s", conversation_id, type(exc).__name__)
        return _agent_error("unknown")


def delete_hermes_session(session_id: str, paths: RuntimePaths | None = None) -> bool:
    runtime_paths = paths or ensure_runtime_dirs()
    try:
        _AIAgent, SessionDB = _load_hermes_classes(runtime_paths)
        session_db = SessionDB()
        return bool(session_db.delete_session(session_id, runtime_paths.hermes_home / "sessions"))
    except Exception as exc:
        logger.warning("Hermes session delete failed session=%s error=%s", session_id, type(exc).__name__)
        return False
