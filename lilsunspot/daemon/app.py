from __future__ import annotations

import platform
import os
import webbrowser
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lilsunspot import __version__

from . import conversations
from .audit import ensure_audit_schema, list_audit_events, record_audit_event
from .attachments import AttachmentError, is_safe_stored_attachment
from .auth import load_or_create_token, require_token
from .agent_runner import delete_hermes_session, send_agent_message
from .capabilities import (
    CapabilityError,
    get_capability,
    get_platform_toolsets,
    list_capabilities,
    save_platform_toolsets,
    test_capability,
    update_capability,
)
from .chat_client import current_runtime_model
from .config_paths import ensure_runtime_dirs
from .diagnostics import export_diagnostics
from .doctor import repair_placeholder, run_doctor_checks
from .gateway import (
    WeixinGatewayError,
    disconnect_weixin,
    handle_weixin_command_text,
    poll_weixin_login_status,
    request_weixin_send_approval,
    start_weixin_login,
    weixin_commands,
    weixin_status,
)
from .hermes_compat import audit_hermes_compatibility
from .hermes_runtime import (
    HermesRuntimeError,
    delete_mcp_server,
    list_mcp_servers,
    model_runtime_config,
    save_auxiliary_model,
    save_fallback_providers,
    save_provider_credentials,
    save_provider_routing,
    upsert_mcp_server,
)
from .logging_utils import configure_logging
from .mode_intents import apply_mode_intent
from .modes import get_current_mode, load_mode_profiles, select_mode
from .provider_client import test_provider_connection
from .providers import load_provider_registry, provider_by_id
from .runtime_discovery import base_url_for, write_runtime_descriptor
from .safety import (
    ApprovalNotFoundError,
    decide_approval,
    describe_approval_placeholder,
    list_pending_approvals,
    load_safety_policy,
    request_safety_approval,
)
from .weixin_runtime import start_weixin_runtime, stop_weixin_runtime, weixin_runtime_status


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _configured_host() -> str:
    host = os.environ.get("LILSUNSPOT_BIND_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    if host != DEFAULT_HOST:
        raise RuntimeError("lilsunspotd 只能绑定到 127.0.0.1。")
    return host


def _configured_port() -> int:
    raw_port = os.environ.get("LILSUNSPOT_BIND_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("lilsunspotd 端口不正确。") from exc
    if port < 1 or port > 65535:
        raise RuntimeError("lilsunspotd 端口不正确。")
    return port


BIND_HOST = _configured_host()
BIND_PORT = _configured_port()

paths = ensure_runtime_dirs()
os.environ["HERMES_HOME"] = str(paths.hermes_home)
logger = configure_logging(paths.logs_dir)
load_or_create_token()
runtime_descriptor = write_runtime_descriptor(BIND_HOST, BIND_PORT, paths)
conversations.ensure_schema(paths)
ensure_audit_schema(paths)
logger.info(
    "daemon runtime discovery written base_url=%s pid=%s",
    runtime_descriptor["base_url"],
    runtime_descriptor["pid"],
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if current_runtime_model(paths)["configured"]:
        await start_weixin_runtime(paths)
    try:
        yield
    finally:
        await stop_weixin_runtime()


app = FastAPI(
    title="lilsunspotd",
    version=__version__,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Lilsunspot-Token", "Last-Event-ID"],
)


def _with_weixin_runtime_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "runtime": weixin_runtime_status()}


class OpenKeyUrlRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    open_browser: bool = False


class SaveProviderRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    api_key: str = ""
    base_url_override: str | None = None


class ProviderTestRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str | None = None
    api_key: str = ""
    base_url_override: str | None = None


class CapabilityPatchRequest(BaseModel):
    enabled: bool | None = None


class ModelFallbacksRequest(BaseModel):
    fallbacks: list[dict[str, Any]] = Field(default_factory=list)


class ModelRoutingRequest(BaseModel):
    routing: dict[str, Any] = Field(default_factory=dict)


class ModelAuxiliaryRequest(BaseModel):
    task: str = Field(..., min_length=1)
    provider: str = ""
    model: str = ""
    base_url: str = ""


class PlatformToolsetsRequest(BaseModel):
    toolsets: list[str] = Field(default_factory=list)


class McpServerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class McpServerPatchRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


class ConversationMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ConversationCreateRequest(BaseModel):
    title: str | None = None
    kind: str = "desktop"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None
    weixin_route_active: bool | None = None


class SelectModeRequest(BaseModel):
    mode: str = Field(..., min_length=1)
    style_axis: int | None = None
    detail_level: int | None = None
    autonomy_level: int | None = None


class ApprovalPlaceholderRequest(BaseModel):
    operation: str = Field(..., min_length=1)


class ApprovalRequest(BaseModel):
    operation: str = Field(..., min_length=1)
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    source: str = "local_api"


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., min_length=1)


class WeixinCommandRequest(BaseModel):
    text: str = Field(..., min_length=1)


class WeixinSendRequest(BaseModel):
    recipient: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    attachment_ids: list[str] = Field(default_factory=list)


class RepairRequest(BaseModel):
    check_name: str | None = None


@app.get("/health")
async def health() -> dict[str, Any]:
    runtime_model = current_runtime_model(ensure_runtime_dirs())
    return {
        "ok": True,
        "status": "ready",
        "message_cn": "小黑子本地服务正常",
        "setup_required": not runtime_model["configured"],
        "version": __version__,
    }


@app.get("/app/state", dependencies=[Depends(require_token)])
async def app_state() -> dict[str, str]:
    runtime_model = current_runtime_model(ensure_runtime_dirs())
    if runtime_model["configured"]:
        return {
            "boot": "chat_ready",
            "title": "小黑子已准备好",
            "message": "模型服务已配置，可以开始聊天。",
            "next_action": "open_chat",
        }
    return {
        "boot": "provider_missing",
        "title": "还差一步：选择模型服务",
        "message": "小黑子已经启动，但还没有配置可用的模型。",
        "next_action": "open_provider_wizard",
    }


def _action(action_id: str, label: str) -> dict[str, str]:
    return {"id": action_id, "label": label}


def _app_bootstrap_state() -> dict[str, Any]:
    runtime_model = current_runtime_model(ensure_runtime_dirs())
    configured = bool(runtime_model["configured"])
    provider_id = str(runtime_model.get("provider") or "")
    model = str(runtime_model.get("model") or "")
    provider_config = provider_by_id(provider_id) if provider_id else None
    weixin_state = weixin_status()
    if weixin_state.get("connected"):
        weixin_check = "connected"
    elif weixin_state.get("available"):
        weixin_check = "not_configured"
    else:
        weixin_check = "unavailable"

    checks = {
        "daemon": "ok",
        "model_config": "present" if configured and provider_config else "missing" if not configured else "invalid",
        "chat": "ready" if configured and provider_config else "blocked",
        "mode": "ready",
        "weixin": weixin_check,
        "safety": "placeholder",
    }
    runtime = {
        "configured": bool(configured and provider_config),
        "provider": provider_id if provider_config else "",
        "model": model if provider_config else "",
    }

    if configured and provider_config:
        return {
            "stage": "chat_ready",
            "title": "小黑子已准备好",
            "message": "AI 服务已设置，可以直接开始聊天。",
            "primary_action": _action("open_chat", "开始聊天"),
            "secondary_actions": [_action("open_settings", "打开设置")],
            "checks": checks,
            "runtime": runtime,
            "user_visible_blockers": [],
        }

    if configured and provider_config is None:
        return {
            "stage": "repair_required",
            "title": "模型服务设置需要修复",
            "message": "已保存的 AI 服务不在当前支持列表里，请重新选择一个服务。",
            "primary_action": _action("setup_model", "重新设置"),
            "secondary_actions": [_action("open_doctor", "一键检查")],
            "checks": checks,
            "runtime": runtime,
            "user_visible_blockers": [
                {
                    "code": "invalid_model_config",
                    "message": "已保存的 AI 服务不可用。",
                    "suggestion": "请重新选择 AI 服务并测试保存。",
                }
            ],
        }

    return {
        "stage": "needs_model",
        "title": "还差一步：设置 AI 服务",
        "message": "先给小黑子设置一个 AI 服务，就能开始聊天。",
        "primary_action": _action("setup_model", "开始设置"),
        "secondary_actions": [_action("open_doctor", "一键检查")],
        "checks": checks,
        "runtime": runtime,
        "user_visible_blockers": [
            {
                "code": "missing_model",
                "message": "还没有设置 AI 服务。",
                "suggestion": "先完成模型服务设置。",
            }
        ],
    }


@app.get("/app/bootstrap", dependencies=[Depends(require_token)])
async def app_bootstrap() -> dict[str, Any]:
    return _app_bootstrap_state()


@app.get("/runtime/info", dependencies=[Depends(require_token)])
async def runtime_info() -> dict[str, Any]:
    runtime_paths = ensure_runtime_dirs()
    runtime_model = current_runtime_model(runtime_paths)
    compatibility = audit_hermes_compatibility()
    return {
        "data_dir": str(runtime_paths.data_dir),
        "hermes_home": str(runtime_paths.hermes_home),
        "logs_dir": str(runtime_paths.logs_dir),
        "platform": platform.platform(),
        "daemon_version": __version__,
        "bind_host": BIND_HOST,
        "bind_port": BIND_PORT,
        "base_url": base_url_for(BIND_HOST, BIND_PORT),
        "pid": os.getpid(),
        "runtime_file": str(runtime_paths.runtime_file),
        "configured": runtime_model["configured"],
        "provider": runtime_model["provider"],
        "model": runtime_model["model"],
        "hermes_compatibility": {
            "ok": compatibility["ok"],
            "hermes_version": compatibility["hermes_version"],
            "upstream_commit": compatibility["upstream_commit"],
        },
    }


@app.get("/providers", dependencies=[Depends(require_token)])
async def providers() -> dict[str, list[dict[str, Any]]]:
    return {"providers": load_provider_registry()}


@app.post("/providers/open-key-url", dependencies=[Depends(require_token)])
async def open_key_url(payload: OpenKeyUrlRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="没有找到这个模型服务商。")
    key_url = str(provider.get("key_url") or provider.get("detect_url") or "").strip()
    if not key_url:
        raise HTTPException(status_code=400, detail="这个服务商没有配置 Key 获取地址。")
    opened = False
    if payload.open_browser:
        opened = bool(webbrowser.open(key_url))
    return {"provider": str(provider["id"]), "key_url": key_url, "opened": opened}


@app.post("/providers/test", dependencies=[Depends(require_token)])
async def providers_test(payload: ProviderTestRequest) -> dict[str, Any]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        return {
            "ok": False,
            "provider": payload.provider,
            "model": payload.model or "",
            "error_code": "unknown",
            "title": "没有找到这个模型服务",
            "message": "没有找到这个模型服务商。",
            "actions": ["重新选择模型服务", "查看技术详情"],
            "suggestion": "重新选择模型服务",
            "safe_details": {
                "provider": payload.provider,
                "masked_key": "",
                "http_status": 404,
            },
        }
    return await test_provider_connection(provider, payload.model, payload.api_key, payload.base_url_override or "")


@app.post("/providers/save", dependencies=[Depends(require_token)])
async def save_provider(payload: SaveProviderRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="没有找到这个模型服务商。")
    try:
        result = save_provider_credentials(provider, payload.model, payload.api_key, payload.base_url_override or "")
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("provider saved provider=%s model=%s", result["provider"], result["model"])
    record_audit_event(
        "config_change",
        "更新了主模型配置。",
        source="providers.save",
        details={"provider": result["provider"], "model": result["model"]},
        paths=paths,
    )
    return {
        "ok": True,
        "provider": result["provider"],
        "model": result["model"],
        "hermes_home": str(ensure_runtime_dirs().hermes_home),
    }


@app.get("/capabilities", dependencies=[Depends(require_token)])
async def capabilities() -> dict[str, Any]:
    return list_capabilities(paths)


@app.get("/capabilities/{capability_id}", dependencies=[Depends(require_token)])
async def capability_detail(capability_id: str) -> dict[str, Any]:
    try:
        return {"capability": get_capability(capability_id, paths)}
    except CapabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/capabilities/{capability_id}", dependencies=[Depends(require_token)])
async def capability_update(capability_id: str, payload: CapabilityPatchRequest) -> dict[str, Any]:
    try:
        capability = update_capability(capability_id, enabled=payload.enabled, paths=paths)
    except CapabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "capability_update",
        "更新了能力开关。",
        source="capabilities",
        details={"capability_id": capability_id, "enabled": payload.enabled},
        paths=paths,
    )
    return {"ok": True, "capability": capability}


@app.post("/capabilities/{capability_id}/test", dependencies=[Depends(require_token)])
async def capability_test(capability_id: str) -> dict[str, Any]:
    try:
        result = test_capability(capability_id, paths)
    except CapabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit_event(
        "capability_test",
        "检查了能力状态。",
        source="capabilities",
        details={"capability_id": capability_id, "ok": result.get("ok")},
        paths=paths,
    )
    return result


@app.get("/models/runtime", dependencies=[Depends(require_token)])
async def models_runtime() -> dict[str, Any]:
    return model_runtime_config(paths)


@app.post("/models/main", dependencies=[Depends(require_token)])
async def models_main(payload: SaveProviderRequest) -> dict[str, Any]:
    return await save_provider(payload)


@app.post("/models/fallbacks", dependencies=[Depends(require_token)])
async def models_fallbacks(payload: ModelFallbacksRequest) -> dict[str, Any]:
    try:
        result = save_fallback_providers(payload.fallbacks, paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "config_change",
        "更新了备用模型链。",
        source="models.fallbacks",
        details={"count": len(payload.fallbacks)},
        paths=paths,
    )
    return {"ok": True, "models": result}


@app.post("/models/routing", dependencies=[Depends(require_token)])
async def models_routing(payload: ModelRoutingRequest) -> dict[str, Any]:
    try:
        result = save_provider_routing(payload.routing, paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "config_change",
        "更新了模型路由配置。",
        source="models.routing",
        details={"keys": sorted(payload.routing.keys())},
        paths=paths,
    )
    return {"ok": True, "models": result}


@app.post("/models/auxiliary", dependencies=[Depends(require_token)])
async def models_auxiliary(payload: ModelAuxiliaryRequest) -> dict[str, Any]:
    try:
        result = save_auxiliary_model(payload.task, payload.provider, payload.model, payload.base_url, paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "config_change",
        "更新了辅助模型配置。",
        source="models.auxiliary",
        details={"task": payload.task, "provider": payload.provider, "model": payload.model},
        paths=paths,
    )
    return {"ok": True, "models": result}


@app.get("/tools/platform/lilsunspot", dependencies=[Depends(require_token)])
async def tools_platform_lilsunspot() -> dict[str, Any]:
    return get_platform_toolsets(paths)


@app.put("/tools/platform/lilsunspot", dependencies=[Depends(require_token)])
async def tools_platform_lilsunspot_update(payload: PlatformToolsetsRequest) -> dict[str, Any]:
    try:
        result = save_platform_toolsets(payload.toolsets, paths)
    except CapabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "config_change",
        "更新了小黑子工具集。",
        source="tools.platform",
        details={"toolsets": payload.toolsets},
        paths=paths,
    )
    return {"ok": True, **result}


@app.get("/mcp/servers", dependencies=[Depends(require_token)])
async def mcp_servers() -> dict[str, Any]:
    return list_mcp_servers(paths)


@app.post("/mcp/servers", dependencies=[Depends(require_token)])
async def mcp_server_create(payload: McpServerCreateRequest) -> dict[str, Any]:
    try:
        result = upsert_mcp_server(payload.name, payload.config, paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "mcp_config_change",
        "新增或更新了 MCP 服务。",
        source="mcp",
        details={"name": payload.name, "config": payload.config},
        paths=paths,
    )
    return {"ok": True, **result}


@app.patch("/mcp/servers/{name}", dependencies=[Depends(require_token)])
async def mcp_server_update(name: str, payload: McpServerPatchRequest) -> dict[str, Any]:
    try:
        result = upsert_mcp_server(name, payload.config, paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "mcp_config_change",
        "更新了 MCP 服务。",
        source="mcp",
        details={"name": name, "config": payload.config},
        paths=paths,
    )
    return {"ok": True, **result}


@app.delete("/mcp/servers/{name}", dependencies=[Depends(require_token)])
async def mcp_server_delete(name: str) -> dict[str, Any]:
    try:
        result = delete_mcp_server(name, paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        "mcp_config_change",
        "删除了 MCP 服务。",
        source="mcp",
        details={"name": name},
        paths=paths,
    )
    return {"ok": True, **result}


@app.get("/modes", dependencies=[Depends(require_token)])
async def modes() -> dict[str, Any]:
    return {"modes": load_mode_profiles()}


@app.get("/modes/current", dependencies=[Depends(require_token)])
async def modes_current() -> dict[str, Any]:
    return get_current_mode()


@app.post("/modes/select", dependencies=[Depends(require_token)])
async def modes_select(payload: SelectModeRequest) -> dict[str, Any]:
    try:
        return select_mode(
            payload.mode,
            style_axis=payload.style_axis,
            detail_level=payload.detail_level,
            autonomy_level=payload.autonomy_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chat/send", dependencies=[Depends(require_token)])
async def chat_send(payload: ChatSendRequest) -> dict[str, Any]:
    result = await _send_conversation_message(
        payload.message,
        conversation_id=payload.conversation_id or conversations.PERSONAL_CONVERSATION_ID,
        source="desktop",
    )
    return result["chat"]


async def _send_conversation_message(
    message: str,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    source: str = "desktop",
) -> dict[str, Any]:
    runtime_paths = ensure_runtime_dirs()
    user_message = conversations.create_message(
        conversation_id=conversation_id,
        source=source,
        role="user",
        text=message,
        status="sent",
        metadata={"entry": source},
    )
    mode_intent = await apply_mode_intent(message, runtime_paths)
    if mode_intent is not None:
        assistant_message = conversations.create_message(
            conversation_id=conversation_id,
            source="assistant",
            role="assistant",
            text=str(mode_intent.get("message") or ""),
            status="sent",
            metadata={
                "kind": "mode_intent",
                "changed": mode_intent.get("changed"),
                "mode": (mode_intent.get("mode") or {}).get("current") if isinstance(mode_intent.get("mode"), dict) else None,
            },
        )
        runtime_model = current_runtime_model(runtime_paths)
        return {
            "ok": True,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "chat": {
                "ok": True,
                "reply": assistant_message["text"],
                "engine": "lilsunspot_mode_router",
                "provider": runtime_model.get("provider") or "",
                "model": runtime_model.get("model") or "",
                "conversation_id": None,
                "conversation_id_supported": False,
                "conversation_id_requested": bool(conversation_id),
                "mode_intent": mode_intent.get("intent"),
                "mode": mode_intent.get("mode"),
            },
        }
    chat_result = await send_agent_message(
        message,
        conversation_id,
        runtime_paths,
        current_message_id=user_message["id"],
    )
    if chat_result.get("ok"):
        assistant_message = conversations.create_message(
            conversation_id=conversation_id,
            source="assistant",
            role="assistant",
            text=str(chat_result.get("reply") or ""),
            status="sent",
            metadata={
                "engine": chat_result.get("engine"),
                "provider": chat_result.get("provider"),
                "model": chat_result.get("model"),
                "hermes_session_id": chat_result.get("hermes_session_id"),
            },
        )
    else:
        assistant_message = conversations.create_message(
            conversation_id=conversation_id,
            source="assistant",
            role="assistant",
            text=f"{chat_result.get('message', '聊天请求没有成功。')}\n{chat_result.get('suggestion', '')}".strip(),
            status="error",
            metadata={"error_code": chat_result.get("error_code")},
        )
    return {"ok": bool(chat_result.get("ok")), "user_message": user_message, "assistant_message": assistant_message, "chat": chat_result}


@app.get("/conversations", dependencies=[Depends(require_token)])
async def api_conversations(include_archived: bool = False) -> dict[str, Any]:
    return {"conversations": conversations.list_conversations(include_archived=include_archived)}


@app.post("/conversations", dependencies=[Depends(require_token)])
async def api_conversation_create(payload: ConversationCreateRequest) -> dict[str, Any]:
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    kind = (payload.kind or "desktop").strip() or "desktop"
    route = metadata.get("weixin_route") if isinstance(metadata.get("weixin_route"), dict) else None
    if kind == "weixin" and route:
        conversation = conversations.create_weixin_conversation(route, title=payload.title)
    else:
        conversation = conversations.create_conversation(title=payload.title, kind=kind, metadata=metadata)
    return {"conversation": conversation}


@app.get("/conversations/{conversation_id}/messages", dependencies=[Depends(require_token)])
async def api_conversation_messages(
    conversation_id: str,
    after_id: str | None = None,
    limit: int = conversations.DEFAULT_MESSAGE_LIMIT,
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "messages": conversations.list_messages(conversation_id, after_id=after_id, limit=limit),
    }


@app.post("/conversations/{conversation_id}/messages", dependencies=[Depends(require_token)])
async def api_conversation_message_send(
    conversation_id: str,
    payload: ConversationMessageRequest,
) -> dict[str, Any]:
    return await _send_conversation_message(payload.message, conversation_id=conversation_id, source="desktop")


@app.patch("/conversations/{conversation_id}", dependencies=[Depends(require_token)])
async def api_conversation_update(
    conversation_id: str,
    payload: ConversationUpdateRequest,
) -> dict[str, Any]:
    if payload.weixin_route_active is True:
        conversation = conversations.set_weixin_conversation_active(conversation_id)
    else:
        conversation = conversations.update_conversation(
            conversation_id,
            title=payload.title,
            archived=payload.archived,
        )
    if conversation is None:
        raise HTTPException(status_code=404, detail="没有找到这个对话。")
    return {"conversation": conversation}


@app.delete("/conversations/{conversation_id}", dependencies=[Depends(require_token)])
async def api_conversation_delete(conversation_id: str) -> dict[str, Any]:
    conversation = conversations.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="没有找到这个对话。")
    session_id = conversations.hermes_session_id(conversation, conversation_id)
    deleted = conversations.delete_conversation(conversation_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="没有找到这个对话。")
    hermes_deleted = delete_hermes_session(session_id)
    return {
        "ok": True,
        "conversation_id": conversation_id,
        "hermes_session_id": session_id,
        "hermes_deleted": hermes_deleted,
    }


@app.get("/attachments/{attachment_id}", dependencies=[Depends(require_token)])
async def api_attachment(attachment_id: str) -> dict[str, Any]:
    attachment = conversations.get_attachment(attachment_id, include_safe_path=True)
    if attachment is None:
        raise HTTPException(status_code=404, detail="没有找到这个附件。")
    try:
        safe_path = is_safe_stored_attachment(str(attachment.get("safe_path") or ""))
    except AttachmentError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    attachment["safe_path"] = str(safe_path)
    return {"attachment": attachment}


@app.get("/events/stream", dependencies=[Depends(require_token)])
async def api_events_stream(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    try:
        cursor = int(last_event_id or request.query_params.get("after_id") or "0")
    except ValueError:
        cursor = 0

    async def event_stream():
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                break
            events = await conversations.wait_for_events_after(cursor, timeout_seconds=15.0)
            if not events:
                yield ": keepalive\n\n"
                continue
            for event in events:
                cursor = int(event["id"])
                yield conversations.format_sse_event(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/gateway/weixin/status", dependencies=[Depends(require_token)])
async def gateway_weixin_status() -> dict[str, Any]:
    return _with_weixin_runtime_status(weixin_status())


@app.post("/gateway/weixin/login/start", dependencies=[Depends(require_token)])
async def gateway_weixin_login_start() -> dict[str, Any]:
    try:
        return _with_weixin_runtime_status(await start_weixin_login())
    except WeixinGatewayError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/gateway/weixin/login/status", dependencies=[Depends(require_token)])
async def gateway_weixin_login_status() -> dict[str, Any]:
    result = await poll_weixin_login_status()
    if result.get("connected"):
        await start_weixin_runtime(paths)
    return _with_weixin_runtime_status(result)


@app.post("/gateway/weixin/disconnect", dependencies=[Depends(require_token)])
async def gateway_weixin_disconnect() -> dict[str, Any]:
    await stop_weixin_runtime()
    return _with_weixin_runtime_status(disconnect_weixin())


@app.get("/gateway/weixin/commands", dependencies=[Depends(require_token)])
async def gateway_weixin_commands() -> dict[str, Any]:
    return weixin_commands()


@app.post("/gateway/weixin/commands/handle", dependencies=[Depends(require_token)])
async def gateway_weixin_command_handle(payload: WeixinCommandRequest) -> dict[str, Any]:
    return await handle_weixin_command_text(payload.text)


@app.post("/gateway/weixin/send", dependencies=[Depends(require_token)])
async def gateway_weixin_send(payload: WeixinSendRequest) -> dict[str, Any]:
    try:
        return request_weixin_send_approval(payload.recipient, payload.message, payload.attachment_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/safety/policy", dependencies=[Depends(require_token)])
async def safety_policy() -> dict[str, Any]:
    return {"policy": load_safety_policy()}


@app.get("/safety/approvals", dependencies=[Depends(require_token)])
async def safety_approvals() -> dict[str, Any]:
    return list_pending_approvals()


@app.get("/safety/audit", dependencies=[Depends(require_token)])
async def safety_audit(limit: int = 100) -> dict[str, Any]:
    return list_audit_events(limit=limit, paths=paths)


@app.post("/safety/approvals/request", dependencies=[Depends(require_token)])
async def safety_approval_request(payload: ApprovalRequest) -> dict[str, Any]:
    try:
        result = request_safety_approval(
            payload.operation,
            payload.summary or f"请求执行 {payload.operation}",
            payload.details,
            payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/safety/approvals/{approval_id}/decide", dependencies=[Depends(require_token)])
async def safety_approval_decide(approval_id: str, payload: ApprovalDecisionRequest) -> dict[str, Any]:
    try:
        result = decide_approval(approval_id, payload.decision)
    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result["approval"].get("status") == "approved" and result["approval"].get("operation") == "send_weixin_message":
        from .weixin_runtime import send_approved_weixin_action

        result["delivery"] = await send_approved_weixin_action(result["approval"])
        conversations.append_event(
            "approval.delivery_updated",
            {"approval": result["approval"], "delivery": result["delivery"]},
        )
    return result


@app.post("/safety/approvals/placeholder", dependencies=[Depends(require_token)])
async def safety_approval_placeholder(payload: ApprovalPlaceholderRequest) -> dict[str, Any]:
    return describe_approval_placeholder(payload.operation)


@app.get("/doctor/run", dependencies=[Depends(require_token)])
async def doctor_run() -> dict[str, Any]:
    return run_doctor_checks()


@app.post("/doctor/repair", dependencies=[Depends(require_token)])
async def doctor_repair(payload: RepairRequest) -> dict[str, Any]:
    return repair_placeholder(payload.check_name)


@app.post("/doctor/diagnostics/export", dependencies=[Depends(require_token)])
async def doctor_diagnostics_export() -> dict[str, Any]:
    return export_diagnostics(paths)


def main() -> None:
    import uvicorn

    uvicorn.run("lilsunspot.daemon.app:app", host=BIND_HOST, port=BIND_PORT, reload=False)


if __name__ == "__main__":
    main()
