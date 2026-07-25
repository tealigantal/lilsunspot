from __future__ import annotations

import asyncio
import copy
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import conversations
from . import provider_client as provider_http
from .agent_host import AgentHostCallbacks, clear_active_turn, register_active_turn
from .capabilities import enabled_toolsets_for_agent, fallback_chain_for_agent
from .chat_client import CHAT_ERROR_MESSAGES, _chat_error, _load_chat_settings
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .delivery_actions import deliverable_dir_for_turn, delivery_turn_context
from .delivery_tools import LILSUNSPOT_DELIVERY_TOOLSET, register_delivery_tools
from .generation_controls import (
    public_execution_trace,
    record_parameter_rejection,
    rejected_parameter_from_error,
    resolve_generation_control,
)
from .media_delivery import generated_file_delivery_prompt
from .mode_tools import LILSUNSPOT_MODE_TOOLSET, register_mode_tools
from .prompt_layers import compile_product_prompt_layers


logger = logging.getLogger(__name__)
AGENT_ENGINE = "hermes_agent_loop"
_IMPORT_LOCK = threading.Lock()
_AGENT_TURN_LOCK = threading.Lock()


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


def _settings_for_agent(
    paths: RuntimePaths,
    *,
    conversation_id: str | None = None,
    turn_override: dict[str, Any] | None = None,
    generation_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    error, settings = _load_chat_settings(paths, conversation_id=conversation_id, turn_override=turn_override)
    if error is not None:
        return error, None
    assert settings is not None
    try:
        base_url = provider_http._provider_base_url(settings["provider_config"])
    except provider_http.ProviderValidationError:
        return _agent_error("provider_required"), None
    provider_config = settings["provider_config"]
    hermes_provider = str(provider_config.get("hermes_provider") or settings["provider"]).strip() or "custom"
    mode_overlay = str(settings.get("system_hint") or "").strip()
    fallback_chain = fallback_chain_for_agent(paths)
    generation_control = resolve_generation_control(
        paths,
        provider=str(settings["provider"]),
        hermes_provider=hermes_provider,
        model=str(settings["model"]),
        conversation_id=conversation_id,
        turn_override=generation_override,
        fallback_chain=fallback_chain,
    )
    reasoning_effort = generation_control["runtime"].get("reasoning_effort")
    reasoning_config = None
    if reasoning_effort == "none":
        reasoning_config = {"enabled": False}
    elif reasoning_effort:
        reasoning_config = {"enabled": True, "effort": reasoning_effort}
    prompt_layers = compile_product_prompt_layers(
        paths,
        mode_overlay=mode_overlay,
    )
    settings = {
        **settings,
        "mode_overlay": mode_overlay,
        "generation_control": generation_control,
        "generation_reasoning_config": reasoning_config,
        "fallback_chain": fallback_chain,
        "system_hint": prompt_layers.compile(),
        "prompt_layers": prompt_layers.summaries(),
    }
    return None, {**settings, "base_url": base_url, "hermes_provider": hermes_provider}


def generation_control_status(
    paths: RuntimePaths,
    *,
    conversation_id: str | None = None,
    generation_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    error, settings = _settings_for_agent(
        paths,
        conversation_id=conversation_id,
        generation_override=generation_override,
    )
    if error is not None:
        return error, None
    assert settings is not None
    return None, dict(settings["generation_control"])


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
    register_mode_tools()
    toolsets = list(enabled_toolsets_for_agent(paths))
    if "file" not in toolsets:
        toolsets.append("file")
    if LILSUNSPOT_DELIVERY_TOOLSET not in toolsets:
        toolsets.append(LILSUNSPOT_DELIVERY_TOOLSET)
    if LILSUNSPOT_MODE_TOOLSET not in toolsets:
        toolsets.append(LILSUNSPOT_MODE_TOOLSET)
    return toolsets


@contextmanager
def _temporary_env(name: str, value: str) -> Any:
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


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
    host_message_id: str | None = None,
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
        turn_id = current_message_id or f"turn_{session_id}"
        deliverable_dir = deliverable_dir_for_turn(paths, conversation_id, turn_id)
        deliverable_dir.mkdir(parents=True, exist_ok=True)
        prompt_layers = compile_product_prompt_layers(
            paths,
            mode_overlay=str(settings.get("mode_overlay") or "").strip(),
            delivery_overlay=generated_file_delivery_prompt(deliverable_dir),
        )
        system_prompt = prompt_layers.compile()
        raw_generation_control = settings.get("generation_control")
        if not isinstance(raw_generation_control, dict):
            raw_generation_control = resolve_generation_control(
                paths,
                provider=str(settings.get("provider") or "custom"),
                hermes_provider=str(settings.get("hermes_provider") or settings.get("provider") or "custom"),
                model=str(settings.get("model") or ""),
                conversation_id=conversation_id,
                fallback_chain=list(settings.get("fallback_chain") or []),
            )
        generation_control = copy.deepcopy(raw_generation_control)
        host_callbacks = AgentHostCallbacks(
            conversation_id=conversation_id,
            message_id=host_message_id,
            source=platform_name,
            paths=paths,
        )
        with _AGENT_TURN_LOCK:
            with _temporary_env("HERMES_WRITE_SAFE_ROOT", str(deliverable_dir)):
                with delivery_turn_context(
                    conversation_id=conversation_id,
                    source=platform_name,
                    route=route,
                    paths=paths,
                    deliverable_dir=deliverable_dir,
                ) as delivery_context:
                    retry_count = 0
                    while True:
                        runtime = generation_control["runtime"]
                        reasoning_effort = runtime.get("reasoning_effort")
                        reasoning_config = None
                        if reasoning_effort == "none":
                            reasoning_config = {"enabled": False}
                        elif reasoning_effort:
                            reasoning_config = {"enabled": True, "effort": reasoning_effort}
                        agent = AIAgent(
                            model=settings["model"],
                            provider=settings["hermes_provider"],
                            base_url=settings["base_url"],
                            api_key=settings["api_key"],
                            enabled_toolsets=_enabled_toolsets_for_lilsunspot_agent(paths),
                            fallback_model=settings.get("fallback_chain") or [],
                            quiet_mode=True,
                            verbose_logging=False,
                            max_iterations=int(runtime.get("max_iterations") or 90),
                            max_tokens=runtime.get("max_tokens"),
                            reasoning_config=reasoning_config,
                            request_overrides=dict(runtime.get("request_overrides") or {}),
                            session_id=session_id,
                            session_db=session_db,
                            platform=platform_name,
                            user_id=str((route or {}).get("user_id") or ""),
                            chat_id=conversation_id,
                            chat_name=str(conversation.get("title") or ""),
                            chat_type=str((route or {}).get("chat_type") or ""),
                            gateway_session_key=session_id,
                            skip_context_files=True,
                            load_soul_identity=True,
                            skip_memory=False,
                            ephemeral_system_prompt=system_prompt,
                            tool_progress_callback=host_callbacks.tool_progress_callback,
                            tool_start_callback=host_callbacks.tool_start_callback,
                            tool_complete_callback=host_callbacks.tool_complete_callback,
                            clarify_callback=host_callbacks.clarify_callback,
                            stream_delta_callback=host_callbacks.stream_delta_callback,
                            status_callback=host_callbacks.status_callback,
                        )
                        register_active_turn(conversation_id, agent=agent, message_id=host_message_id, paths=paths)
                        try:
                            result = agent.run_conversation(
                                user_message=message,
                                conversation_history=history,
                                task_id=session_id,
                            )
                        finally:
                            clear_active_turn(conversation_id, agent)
                        result_error = str(result.get("error") or "") if isinstance(result, dict) else ""
                        candidates = list(dict(generation_control.get("effective_parameters") or {}))
                        rejected = rejected_parameter_from_error(result_error, candidates)
                        if retry_count or not rejected:
                            break
                        record_parameter_rejection(paths, settings["provider"], settings["model"], rejected)
                        retry_count = 1
                        generation_control["automatic_downgrade"] = True
                        generation_control["retry_count"] = retry_count
                        generation_control["effective_parameters"].pop(rejected, None)
                        detail = generation_control["parameters"].get(rejected, {})
                        detail.update(
                            {
                                "effective": None,
                                "status": "unsupported",
                                "reason": "Provider 拒绝了此参数，已移除并安全重试一次。",
                                "degraded": True,
                            }
                        )
                        runtime["request_overrides"].pop(rejected, None)
                        if rejected == "max_tokens":
                            runtime["max_tokens"] = None
                        elif rejected == "reasoning_effort":
                            runtime["reasoning_effort"] = None
                    delivery_actions = delivery_context.actions_for_result()
    finally:
        unregister_gateway_notify(session_id)
        reset_current_session_key(approval_token)
        clear_session_vars(tokens)

    if isinstance(result, dict) and result.get("failed"):
        return {
            "ok": False,
            "error_code": "provider_error",
            "message": "模型服务未能完成这次请求。",
            "suggestion": "请查看本次生成详情；如果参数已降级仍失败，可切换模型或恢复模型默认值后重试。",
            "generation_execution": public_execution_trace(
                generation_control,
                tool_iterations=host_callbacks.tool_iterations,
                retry_count=retry_count,
            ),
        }
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
        "generation_execution": public_execution_trace(
            generation_control,
            tool_iterations=host_callbacks.tool_iterations,
            retry_count=retry_count,
        ),
    }


async def send_agent_message(
    message: str,
    conversation_id: str | None = None,
    paths: RuntimePaths | None = None,
    *,
    current_message_id: str | None = None,
    host_message_id: str | None = None,
    exclude_message_ids: list[str] | None = None,
    route: dict[str, str] | None = None,
    turn_override: dict[str, Any] | None = None,
    generation_override: dict[str, Any] | None = None,
    require_existing_conversation: bool = False,
) -> dict[str, Any]:
    conversation_id = (conversation_id or conversations.PERSONAL_CONVERSATION_ID).strip() or conversations.PERSONAL_CONVERSATION_ID
    message = message.strip()
    if not message:
        return _agent_error("empty_message")
    runtime_paths = paths or ensure_runtime_dirs()
    error, settings = _settings_for_agent(
        runtime_paths,
        conversation_id=conversation_id,
        turn_override=turn_override,
        generation_override=generation_override,
    )
    if error is not None:
        return error
    assert settings is not None
    try:
        return await asyncio.to_thread(
            _run_agent_turn,
            message=message,
            conversation_id=conversation_id,
            current_message_id=current_message_id,
            host_message_id=host_message_id,
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
