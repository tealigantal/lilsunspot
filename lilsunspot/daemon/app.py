from __future__ import annotations

import base64
import binascii
import platform
import os
import uuid
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lilsunspot import __version__

from . import conversations, product_features, turn_coalescer
from .agent_host import interrupt_active_turn, steer_active_turn, submit_clarify_answer
from .audit import ensure_audit_schema, list_audit_events, record_audit_event
from .capability_graph import build_capability_graph
from .attachments import (
    AttachmentError,
    DESKTOP_UPLOAD_MAX_BYTES,
    DESKTOP_UPLOAD_MAX_FILES,
    attachment_summaries_for_prompt,
    is_safe_stored_attachment,
    recognize_image_attachments,
    register_uploaded_attachments,
)
from .auth import load_or_create_token, require_token
from .agent_runner import delete_hermes_session, generation_control_status, send_agent_message
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
    fail_weixin_login_verification,
    handle_weixin_command_text,
    poll_weixin_login_status,
    send_weixin_message_direct,
    start_weixin_login,
    weixin_commands,
    weixin_status,
)
from .hermes_compat import audit_hermes_compatibility
from .hermes_runtime import (
    HermesRuntimeError,
    clear_local_model_credentials,
    delete_mcp_server,
    list_mcp_servers,
    model_runtime_config,
    save_auxiliary_model,
    save_fallback_providers,
    save_provider_credentials,
    save_provider_routing,
    upsert_mcp_server,
)
from .generation_controls import (
    GenerationControlError,
    generation_modes_catalog,
    reset_generation_selection,
    save_generation_selection,
)
from .logging_utils import configure_logging
from .media_delivery import add_delivery_context_to_prompt, prepare_assistant_delivery, register_prepared_delivery
from .mode_intents import apply_mode_intent
from .modes import get_current_mode, load_mode_profiles, select_mode
from .provider_client import test_provider_connection
from .providers import load_provider_registry, provider_by_id
from .product_task_scheduler import start_task_scheduler, stop_task_scheduler
from .runtime_discovery import base_url_for, read_runtime_descriptor, write_runtime_descriptor
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
product_features.ensure_schema(paths)
logger.info(
    "daemon runtime discovery written base_url=%s pid=%s",
    runtime_descriptor["base_url"],
    runtime_descriptor["pid"],
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task_scheduler = start_task_scheduler(paths)
    if current_runtime_model(paths)["configured"]:
        await start_weixin_runtime(paths)
    try:
        yield
    finally:
        await stop_task_scheduler()
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


def _with_weixin_runtime_status(payload: dict[str, Any], runtime_status: dict[str, Any] | None = None) -> dict[str, Any]:
    return {**payload, "runtime": runtime_status or weixin_runtime_status()}


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
    api_key: str = ""


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
    generation_override: dict[str, Any] | None = None


class ConversationUploadAttachmentRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    mime_type: str = ""
    data_base64: str = Field(..., min_length=1)


class ConversationMessageRequest(BaseModel):
    message: str = ""
    attachments: list[ConversationUploadAttachmentRequest] = Field(default_factory=list)
    generation_override: dict[str, Any] | None = None


class ConversationTurnStopRequest(BaseModel):
    message: str | None = None


class ConversationTurnSteerRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ConversationBranchRequest(BaseModel):
    title: str | None = None
    message_id: str | None = None


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
    conversation_id: str | None = None
    scope: str | None = None


class GenerationSelectionRequest(BaseModel):
    mode: str | None = None
    parameters: dict[str, Any] | None = None
    conversation_id: str | None = None
    scope: str = "conversation"


class GenerationResetRequest(BaseModel):
    conversation_id: str | None = None
    scope: str = "conversation"


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


class ConversationSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    include_archived: bool = False
    limit: int = 20


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    due_at: str = ""


class ReminderUpdateRequest(BaseModel):
    enabled: bool | None = None
    completed: bool | None = None


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    due_at: str = ""
    kind: str = "reminder"
    schedule: str = "once"


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    prompt: str | None = None
    due_at: str | None = None
    kind: str | None = None
    schedule: str | None = None
    enabled: bool | None = None
    completed: bool | None = None


class MemoryCreateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source: str = "manual"


class MemoryUpdateRequest(BaseModel):
    enabled: bool | None = None


class ProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    instructions: str = Field(..., min_length=1)


class CapabilityUpdateRequest(BaseModel):
    enabled: bool


class AdvancedConfigImportRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


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
            "secondary_actions": [_action("open_settings", "打开设置")],
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
        "secondary_actions": [],
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
    descriptor = read_runtime_descriptor(runtime_paths) or {}
    process = descriptor.get("process") if isinstance(descriptor.get("process"), dict) else {}
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
        "process": process,
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


@app.get("/ui/overview", dependencies=[Depends(require_token)])
async def api_ui_overview() -> dict[str, Any]:
    return product_features.ui_overview(ensure_runtime_dirs())


@app.get("/providers", dependencies=[Depends(require_token)])
async def providers() -> dict[str, list[dict[str, Any]]]:
    return {"providers": load_provider_registry()}


@app.get("/providers/capabilities", dependencies=[Depends(require_token)])
async def provider_capabilities() -> dict[str, Any]:
    return product_features.model_capabilities(ensure_runtime_dirs())


@app.get("/capability-graph", dependencies=[Depends(require_token)])
async def capability_graph() -> dict[str, Any]:
    return build_capability_graph(ensure_runtime_dirs())


@app.post("/providers/open-key-url", dependencies=[Depends(require_token)])
async def open_key_url(payload: OpenKeyUrlRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="没有找到这个模型服务商。")
    key_url = str(provider.get("key_url") or "").strip()
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


@app.post("/providers/reset-local", dependencies=[Depends(require_token)])
async def providers_reset_local() -> dict[str, Any]:
    try:
        result = clear_local_model_credentials(paths)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("provider local credentials reset removed_env_keys=%s", result["removed_env_keys"])
    record_audit_event(
        "config_change",
        "清除了本机 AI 服务设置。",
        source="providers.reset_local",
        details={
            "removed_env_keys": result["removed_env_keys"],
            "cleared_config_keys": result["cleared_config_keys"],
        },
        paths=paths,
    )
    return {
        "ok": True,
        "message": "已清除本机 AI 服务设置，请重新完成首次配置。",
        "removed_env_keys": result["removed_env_keys"],
        "bootstrap": _app_bootstrap_state(),
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
        result = save_auxiliary_model(payload.task, payload.provider, payload.model, payload.base_url, payload.api_key, paths)
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
async def modes_current(conversation_id: str | None = None) -> dict[str, Any]:
    return get_current_mode(conversation_id=conversation_id)


@app.post("/modes/select", dependencies=[Depends(require_token)])
async def modes_select(payload: SelectModeRequest) -> dict[str, Any]:
    try:
        return select_mode(
            payload.mode,
            style_axis=payload.style_axis,
            detail_level=payload.detail_level,
            autonomy_level=payload.autonomy_level,
            conversation_id=payload.conversation_id,
            scope=payload.scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/generation/modes", dependencies=[Depends(require_token)])
async def generation_modes() -> dict[str, Any]:
    return {"modes": generation_modes_catalog()}


@app.get("/generation/current", dependencies=[Depends(require_token)])
async def generation_current(conversation_id: str | None = None) -> dict[str, Any]:
    error, control = generation_control_status(paths, conversation_id=conversation_id)
    if error is not None:
        raise HTTPException(status_code=400, detail=str(error.get("message") or "请先配置 AI 服务。"))
    assert control is not None
    return control


@app.post("/generation/select", dependencies=[Depends(require_token)])
async def generation_select(payload: GenerationSelectionRequest) -> dict[str, Any]:
    selection: dict[str, Any] = {}
    if payload.mode is not None:
        selection["mode"] = payload.mode
    if payload.parameters is not None:
        selection["parameters"] = payload.parameters
    try:
        error, _preview = generation_control_status(
            paths,
            conversation_id=payload.conversation_id,
            generation_override=selection,
        )
        if error is not None:
            raise GenerationControlError(str(error.get("message") or "生成模式没有保存成功。"))
        save_generation_selection(
            paths,
            scope=payload.scope,
            selection=selection,
            conversation_id=payload.conversation_id,
        )
        error, control = generation_control_status(
            paths,
            conversation_id=payload.conversation_id,
            generation_override=selection if payload.scope == "turn" else None,
        )
    except GenerationControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if error is not None:
        raise HTTPException(status_code=400, detail=str(error.get("message") or "生成模式没有保存成功。"))
    assert control is not None
    return control


@app.post("/generation/reset", dependencies=[Depends(require_token)])
async def generation_reset(payload: GenerationResetRequest) -> dict[str, Any]:
    try:
        reset_generation_selection(paths, scope=payload.scope, conversation_id=payload.conversation_id)
        error, control = generation_control_status(paths, conversation_id=payload.conversation_id)
    except GenerationControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if error is not None:
        raise HTTPException(status_code=400, detail=str(error.get("message") or "恢复模型默认值失败。"))
    assert control is not None
    return control


@app.post("/chat/send", dependencies=[Depends(require_token)])
async def chat_send(payload: ChatSendRequest) -> dict[str, Any]:
    result = await _send_conversation_message(
        payload.message,
        conversation_id=payload.conversation_id or conversations.PERSONAL_CONVERSATION_ID,
        source="desktop",
        generation_override=payload.generation_override,
    )
    return result["chat"]


def _assistant_message_from_chat_result(
    chat_result: dict[str, Any],
    *,
    conversation_id: str,
    source: str,
    paths: Any,
    message_id: str | None = None,
    source_message_ids: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_ids = [str(item) for item in (source_message_ids or []) if str(item).strip()]
    prepared = prepare_assistant_delivery(
        str(chat_result.get("reply") or ""),
        conversation_id=conversation_id,
        paths=paths,
        delivery_actions=chat_result.get("delivery_actions") if isinstance(chat_result.get("delivery_actions"), list) else [],
        include_outbound_media=False,
    )
    metadata = {
        "kind": "chat_reply",
        "engine": chat_result.get("engine"),
        "provider": chat_result.get("provider"),
        "model": chat_result.get("model"),
        "hermes_session_id": chat_result.get("hermes_session_id"),
        "delivery": prepared.metadata(),
        "source_message_ids": source_ids,
        "source_message_count": len(source_ids),
        "visible_reply": prepared.visible_text,
        "generation_execution": chat_result.get("generation_execution"),
    }
    if message_id:
        assistant_message = conversations.update_message(
            message_id,
            text=prepared.visible_text,
            status="sent",
            metadata_patch=metadata,
            paths=paths,
        )
        if assistant_message is None:
            assistant_message = conversations.create_message(
                conversation_id=conversation_id,
                source=source,
                role="assistant",
                text=prepared.visible_text,
                status="sent",
                metadata=metadata,
                paths=paths,
            )
    else:
        assistant_message = conversations.create_message(
            conversation_id=conversation_id,
            source=source,
            role="assistant",
            text=prepared.visible_text,
            status="sent",
            metadata=metadata,
            paths=paths,
        )
    try:
        register_prepared_delivery(
            prepared,
            message_id=assistant_message["id"],
            conversation_id=conversation_id,
            source="assistant_delivery",
            paths=paths,
        )
    except AttachmentError:
        assistant_message = conversations.update_message(
            assistant_message["id"],
            metadata_patch={
                "delivery": {
                    "status": "rejected",
                    "delivered_count": 0,
                    "rejected_count": max(1, prepared.rejected_count),
                    "reason_code": "unsafe_path",
                }
            },
            paths=paths,
        ) or assistant_message
    assistant_message = conversations.get_message(assistant_message["id"], paths=paths) or assistant_message
    next_chat = {**chat_result, "reply": prepared.visible_text}
    next_chat.pop("delivery_actions", None)
    return assistant_message, next_chat


def _mode_control_response_message(
    *,
    conversation_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"mode-control-{uuid.uuid4().hex}",
        "conversation_id": conversation_id,
        "source": "system",
        "role": "system",
        "text": text,
        "attachments": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
        "metadata": {"control_event": True, **(metadata or {})},
    }


def _clarify_answer_response(
    *,
    conversation_id: str,
    user_message: dict[str, Any],
    clarify_result: dict[str, Any],
    runtime_paths: Any,
) -> dict[str, Any]:
    runtime_model = current_runtime_model(runtime_paths)
    assistant_message = clarify_result.get("assistant_message") or _mode_control_response_message(
        conversation_id=conversation_id,
        text="已收到，我继续处理。",
        metadata={"kind": "clarify_answer_ack"},
    )
    return {
        "ok": True,
        "accepted": False,
        "turn_id": assistant_message["id"],
        "user_message": user_message,
        "assistant_message": assistant_message,
        "chat": {
            "ok": True,
            "reply": "已收到，我继续处理。",
            "engine": "lilsunspot_hermes_host",
            "provider": runtime_model.get("provider") or "",
            "model": runtime_model.get("model") or "",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
            "clarify_answer": True,
        },
    }


async def _send_conversation_message(
    message: str,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    source: str = "desktop",
    generation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_paths = ensure_runtime_dirs()
    user_message = conversations.create_message(
        conversation_id=conversation_id,
        source=source,
        role="user",
        text=message,
        status="sent",
        metadata={"entry": source},
        paths=runtime_paths,
    )
    clarify_result = submit_clarify_answer(
        conversation_id,
        message,
        message_id=user_message["id"],
        paths=runtime_paths,
    )
    if clarify_result is not None:
        return _clarify_answer_response(
            conversation_id=conversation_id,
            user_message=conversations.get_message(user_message["id"], paths=runtime_paths) or user_message,
            clarify_result=clarify_result,
            runtime_paths=runtime_paths,
        )
    mode_intent = await apply_mode_intent(message, runtime_paths, conversation_id=conversation_id, scope="conversation")
    if mode_intent is not None:
        user_message = conversations.update_message(
            user_message["id"],
            metadata_patch={"kind": "mode_intent_user", "control_event": True},
            paths=runtime_paths,
        ) or user_message
        assistant_message = _mode_control_response_message(
            conversation_id=conversation_id,
            text=str(mode_intent.get("message") or ""),
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
    prompt_text = add_delivery_context_to_prompt(message, conversation_id=conversation_id, paths=runtime_paths)
    chat_result = await send_agent_message(
        prompt_text,
        conversation_id,
        runtime_paths,
        current_message_id=user_message["id"],
        generation_override=generation_override,
    )
    if chat_result.get("ok"):
        assistant_message, chat_result = _assistant_message_from_chat_result(
            chat_result,
            conversation_id=conversation_id,
            source="assistant",
            paths=runtime_paths,
            source_message_ids=[user_message["id"]],
        )
    else:
        assistant_message = conversations.create_message(
            conversation_id=conversation_id,
            source="assistant",
            role="assistant",
            text=f"{chat_result.get('message', '聊天请求没有成功。')}\n{chat_result.get('suggestion', '')}".strip(),
            status="error",
            metadata={
                "error_code": chat_result.get("error_code"),
                "generation_execution": chat_result.get("generation_execution"),
            },
        )
    return {"ok": bool(chat_result.get("ok")), "user_message": user_message, "assistant_message": assistant_message, "chat": chat_result}


def _turn_context_for_conversation(conversation_id: str, runtime_paths: Any) -> dict[str, Any]:
    conversation = conversations.get_conversation(conversation_id, runtime_paths)
    metadata = conversation.get("metadata") if conversation and isinstance(conversation.get("metadata"), dict) else {}
    route = metadata.get("weixin_route") if isinstance(metadata.get("weixin_route"), dict) else None
    if conversation and conversation.get("kind") == "weixin" and route:
        return {
            "assistant_source": "weixin",
            "route": route,
            "turn_key": turn_coalescer.key_for_weixin(route, conversation_id),
        }
    return {
        "assistant_source": "assistant",
        "route": None,
        "turn_key": turn_coalescer.key_for_desktop(conversation_id),
    }


async def _accept_conversation_message(
    message: str,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    source: str = "desktop",
    attachments_payload: list[ConversationUploadAttachmentRequest] | None = None,
    generation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_paths = ensure_runtime_dirs()
    attachments_payload = attachments_payload or []
    message = message.strip()
    if not message and not attachments_payload:
        raise HTTPException(status_code=400, detail="请先输入内容或选择附件。")
    decoded_files: list[dict[str, Any]] = []
    for item in attachments_payload:
        try:
            data = base64.b64decode(item.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail="附件内容格式不正确。") from exc
        decoded_files.append(
            {
                "file_name": item.file_name,
                "mime_type": item.mime_type,
                "data": data,
            }
        )
    if len(decoded_files) > DESKTOP_UPLOAD_MAX_FILES:
        raise HTTPException(status_code=400, detail=f"一次最多上传 {DESKTOP_UPLOAD_MAX_FILES} 个附件。")
    if any(len(item["data"]) > DESKTOP_UPLOAD_MAX_BYTES for item in decoded_files):
        raise HTTPException(status_code=400, detail="单个附件不能超过 25 MB。")
    turn_context = _turn_context_for_conversation(conversation_id, runtime_paths)
    assistant_source = str(turn_context["assistant_source"])
    route = turn_context.get("route") if isinstance(turn_context.get("route"), dict) else None
    user_message = conversations.create_message(
        conversation_id=conversation_id,
        source=source,
        role="user",
        text=message or f"上传了 {len(attachments_payload)} 个附件。",
        status="sent",
        metadata={"entry": source},
        paths=runtime_paths,
    )
    attachments: list[dict[str, Any]] = []
    if decoded_files:
        try:
            attachments = register_uploaded_attachments(
                message_id=user_message["id"],
                conversation_id=conversation_id,
                files=decoded_files,
                source=source,
                paths=runtime_paths,
            )
            attachments = await recognize_image_attachments(attachments, paths=runtime_paths)
        except AttachmentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        user_message = conversations.get_message(user_message["id"], paths=runtime_paths) or user_message

    if message and not attachments:
        clarify_result = submit_clarify_answer(
            conversation_id,
            message,
            message_id=user_message["id"],
            paths=runtime_paths,
        )
        if clarify_result is not None:
            user_message = conversations.get_message(user_message["id"], paths=runtime_paths) or user_message
            return _clarify_answer_response(
                conversation_id=conversation_id,
                user_message=user_message,
                clarify_result=clarify_result,
                runtime_paths=runtime_paths,
            )

    mode_intent = None if attachments else await apply_mode_intent(message, runtime_paths, conversation_id=conversation_id, scope="conversation")
    if mode_intent is not None:
        user_message = conversations.update_message(
            user_message["id"],
            metadata_patch={"kind": "mode_intent_user", "control_event": True},
            paths=runtime_paths,
        ) or user_message
        assistant_message = _mode_control_response_message(
            conversation_id=conversation_id,
            text=str(mode_intent.get("message") or ""),
            metadata={
                "kind": "mode_intent",
                "changed": mode_intent.get("changed"),
                "mode": (mode_intent.get("mode") or {}).get("current") if isinstance(mode_intent.get("mode"), dict) else None,
            },
        )
        runtime_model = current_runtime_model(runtime_paths)
        return {
            "ok": True,
            "accepted": False,
            "turn_id": assistant_message["id"],
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

    if attachments:
        base_text = message or "用户发来了附件，请根据附件处理结果回复。"
        summaries = attachment_summaries_for_prompt(attachments)
        prompt_text = f"{base_text}\n\n以下是用户发来的附件处理结果：\n{summaries}" if summaries else base_text
        prompt_text = add_delivery_context_to_prompt(
            prompt_text,
            attachments=attachments,
            conversation_id=conversation_id,
            paths=runtime_paths,
        )
        assistant_placeholder = conversations.create_message(
            conversation_id=conversation_id,
            source=assistant_source,
            role="assistant",
            text="正在回复...",
            status="generating",
            metadata={
                "kind": "chat_reply_pending",
                "in_reply_to": user_message["id"],
            },
            paths=runtime_paths,
        )
        chat_result = await send_agent_message(
            prompt_text,
            conversation_id,
            runtime_paths,
            current_message_id=user_message["id"],
            host_message_id=assistant_placeholder["id"],
            route=route,
            generation_override=generation_override,
        )
        if chat_result.get("ok"):
            assistant_message, chat_result = _assistant_message_from_chat_result(
                chat_result,
                conversation_id=conversation_id,
                source=assistant_source,
                paths=runtime_paths,
                message_id=assistant_placeholder["id"],
                source_message_ids=[user_message["id"]],
            )
        else:
            assistant_message = conversations.update_message(
                assistant_placeholder["id"],
                text=f"{chat_result.get('message', '聊天请求没有成功。')}\n{chat_result.get('suggestion', '')}".strip(),
                status="error",
                metadata_patch={
                    "error_code": chat_result.get("error_code"),
                    "generation_execution": chat_result.get("generation_execution"),
                },
                paths=runtime_paths,
            ) or assistant_placeholder
        return {
            "ok": bool(chat_result.get("ok")),
            "accepted": False,
            "turn_id": assistant_message["id"],
            "user_message": user_message,
            "assistant_message": assistant_message,
            "chat": chat_result,
        }

    accepted = await turn_coalescer.enqueue_text_turn(
        key=str(turn_context["turn_key"]),
        conversation_id=conversation_id,
        text=message,
        current_message_id=user_message["id"],
        assistant_source=assistant_source,
        paths=runtime_paths,
        route=route,
        generation_override=generation_override,
        wait_for_reply=False,
    )
    if not accepted.get("accepted"):
        raise HTTPException(status_code=404, detail="这个对话已删除，本次回复已取消。")

    runtime_model = current_runtime_model(runtime_paths)
    return {
        "ok": True,
        "accepted": True,
        "turn_id": accepted.get("turn_id"),
        "user_message": user_message,
        "assistant_message": accepted["assistant_message"],
        "chat": {
            "ok": True,
            "accepted": True,
            "reply": "",
            "engine": "lilsunspot_turn_coalescer",
            "provider": runtime_model.get("provider") or "",
            "model": runtime_model.get("model") or "",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        },
    }


@app.get("/conversations", dependencies=[Depends(require_token)])
async def api_conversations(include_archived: bool = False) -> dict[str, Any]:
    return {"conversations": conversations.list_conversations(include_archived=include_archived)}


@app.post("/conversations/search", dependencies=[Depends(require_token)])
async def api_conversation_search(payload: ConversationSearchRequest) -> dict[str, Any]:
    return {
        "query": payload.query,
        "results": product_features.search_conversations(
            payload.query,
            include_archived=payload.include_archived,
            limit=payload.limit,
        ),
    }


@app.post("/sessions/search", dependencies=[Depends(require_token)])
async def api_session_search(payload: ConversationSearchRequest) -> dict[str, Any]:
    return await api_conversation_search(payload)


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
    return await _accept_conversation_message(
        payload.message,
        conversation_id=conversation_id,
        source="desktop",
        attachments_payload=payload.attachments,
        generation_override=payload.generation_override,
    )


@app.post("/conversations/{conversation_id}/turns/stop", dependencies=[Depends(require_token)])
async def api_conversation_turn_stop(
    conversation_id: str,
    payload: ConversationTurnStopRequest,
) -> dict[str, Any]:
    result = interrupt_active_turn(conversation_id, payload.message)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=str(result.get("message") or "当前没有正在执行的任务。"))
    return result


@app.post("/conversations/{conversation_id}/turns/steer", dependencies=[Depends(require_token)])
async def api_conversation_turn_steer(
    conversation_id: str,
    payload: ConversationTurnSteerRequest,
) -> dict[str, Any]:
    result = steer_active_turn(conversation_id, payload.message)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=str(result.get("message") or "当前没有正在执行的任务。"))
    return result


@app.post("/conversations/{conversation_id}/turns/retry", dependencies=[Depends(require_token)])
async def api_conversation_turn_retry(conversation_id: str) -> dict[str, Any]:
    messages = conversations.list_messages(conversation_id, limit=40)
    last_user = next((message for message in reversed(messages) if message.get("role") == "user"), None)
    if last_user is None:
        raise HTTPException(status_code=400, detail="这个对话还没有可重试的用户消息。")
    text = str(last_user.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="上一条用户消息为空，不能重试。")
    result = await _accept_conversation_message(text, conversation_id=conversation_id, source="desktop")
    result["action"] = "retry"
    result["retried_message_id"] = last_user.get("id")
    return result


@app.post("/conversations/{conversation_id}/turns/undo", dependencies=[Depends(require_token)])
async def api_conversation_turn_undo(conversation_id: str) -> dict[str, Any]:
    result = product_features.undo_last_turn(conversation_id, paths=ensure_runtime_dirs())
    if result is None:
        raise HTTPException(status_code=404, detail="没有找到这个对话。")
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("message") or "没有可撤销的消息。"))
    return result


@app.post("/conversations/{conversation_id}/turns/branch", dependencies=[Depends(require_token)])
async def api_conversation_turn_branch(conversation_id: str, payload: ConversationBranchRequest) -> dict[str, Any]:
    result = product_features.branch_conversation(
        conversation_id,
        title=payload.title,
        message_id=payload.message_id,
        paths=ensure_runtime_dirs(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="没有找到这个对话。")
    return result


@app.post("/conversations/{conversation_id}/turns/save-summary", dependencies=[Depends(require_token)])
async def api_conversation_turn_save_summary(conversation_id: str) -> dict[str, Any]:
    try:
        result = product_features.save_conversation_summary(conversation_id, paths=ensure_runtime_dirs())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="没有找到这个对话。")
    return result


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
    runtime_status: dict[str, Any] | None = None
    if result.get("connected"):
        runtime_status = await start_weixin_runtime(paths)
        if not runtime_status.get("running"):
            result = fail_weixin_login_verification(
                runtime_status.get("last_error") or "检测到这次微信登录没有通过同步验证，请刷新二维码后重新扫码。",
                paths,
            )
            runtime_status = weixin_runtime_status()
    return _with_weixin_runtime_status(result, runtime_status)


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
        return await send_weixin_message_direct(payload.recipient, payload.message, payload.attachment_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/safety/policy", dependencies=[Depends(require_token)])
async def safety_policy() -> dict[str, Any]:
    return {"policy": load_safety_policy()}


@app.get("/diagnostics/summary", dependencies=[Depends(require_token)])
async def diagnostics_summary() -> dict[str, Any]:
    return product_features.diagnostics_summary(ensure_runtime_dirs())


@app.get("/reminders", dependencies=[Depends(require_token)])
async def api_reminders() -> dict[str, Any]:
    return {"reminders": product_features.list_reminders()}


@app.post("/reminders", dependencies=[Depends(require_token)])
async def api_reminder_create(payload: ReminderCreateRequest) -> dict[str, Any]:
    try:
        reminder = product_features.create_reminder(title=payload.title, prompt=payload.prompt, due_at=payload.due_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"reminder": reminder}


@app.patch("/reminders/{reminder_id}", dependencies=[Depends(require_token)])
async def api_reminder_update(reminder_id: str, payload: ReminderUpdateRequest) -> dict[str, Any]:
    reminder = product_features.update_reminder(reminder_id, enabled=payload.enabled, completed=payload.completed)
    if reminder is None:
        raise HTTPException(status_code=404, detail="没有找到这个提醒。")
    return {"reminder": reminder}


@app.delete("/reminders/{reminder_id}", dependencies=[Depends(require_token)])
async def api_reminder_delete(reminder_id: str) -> dict[str, Any]:
    deleted = product_features.delete_reminder(reminder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="没有找到这个提醒。")
    return {"ok": True}


@app.get("/tasks", dependencies=[Depends(require_token)])
async def api_tasks() -> dict[str, Any]:
    return {"tasks": product_features.list_tasks(ensure_runtime_dirs())}


@app.post("/tasks", dependencies=[Depends(require_token)])
async def api_task_create(payload: TaskCreateRequest) -> dict[str, Any]:
    try:
        task = product_features.create_task(
            title=payload.title,
            prompt=payload.prompt,
            due_at=payload.due_at,
            kind=payload.kind,
            schedule=payload.schedule,
            paths=ensure_runtime_dirs(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"task": task}


@app.patch("/tasks/{task_id}", dependencies=[Depends(require_token)])
async def api_task_update(task_id: str, payload: TaskUpdateRequest) -> dict[str, Any]:
    try:
        task = product_features.update_task(
            task_id,
            title=payload.title,
            prompt=payload.prompt,
            due_at=payload.due_at,
            kind=payload.kind,
            schedule=payload.schedule,
            enabled=payload.enabled,
            completed=payload.completed,
            paths=ensure_runtime_dirs(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="没有找到这个任务。")
    return {"task": task}


@app.post("/tasks/{task_id}/run", dependencies=[Depends(require_token)])
async def api_task_run(task_id: str) -> dict[str, Any]:
    result = product_features.run_task(task_id, paths=ensure_runtime_dirs())
    if result is None:
        raise HTTPException(status_code=404, detail="没有找到这个任务。")
    return result


@app.delete("/tasks/{task_id}", dependencies=[Depends(require_token)])
async def api_task_delete(task_id: str) -> dict[str, Any]:
    deleted = product_features.delete_reminder(task_id, paths=ensure_runtime_dirs())
    if not deleted:
        raise HTTPException(status_code=404, detail="没有找到这个任务。")
    return {"ok": True}


@app.get("/memory", dependencies=[Depends(require_token)])
async def api_memory() -> dict[str, Any]:
    return {"memories": product_features.list_memories()}


@app.post("/memory", dependencies=[Depends(require_token)])
async def api_memory_create(payload: MemoryCreateRequest) -> dict[str, Any]:
    try:
        memory = product_features.create_memory(text=payload.text, source=payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"memory": memory}


@app.patch("/memory/{memory_id}", dependencies=[Depends(require_token)])
async def api_memory_update(memory_id: str, payload: MemoryUpdateRequest) -> dict[str, Any]:
    memory = product_features.update_memory(memory_id, enabled=payload.enabled)
    if memory is None:
        raise HTTPException(status_code=404, detail="没有找到这条记忆。")
    return {"memory": memory}


@app.delete("/memory/{memory_id}", dependencies=[Depends(require_token)])
async def api_memory_delete(memory_id: str) -> dict[str, Any]:
    deleted = product_features.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="没有找到这条记忆。")
    return {"ok": True}


@app.get("/profiles", dependencies=[Depends(require_token)])
async def api_profiles() -> dict[str, Any]:
    return {"profiles": product_features.list_profiles(ensure_runtime_dirs())}


@app.post("/profiles", dependencies=[Depends(require_token)])
async def api_profile_create(payload: ProfileCreateRequest) -> dict[str, Any]:
    try:
        profile = product_features.create_profile(
            name=payload.name,
            instructions=payload.instructions,
            paths=ensure_runtime_dirs(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"profile": profile}


@app.delete("/profiles/{profile_id}", dependencies=[Depends(require_token)])
async def api_profile_delete(profile_id: str) -> dict[str, Any]:
    deleted = product_features.delete_profile(profile_id, paths=ensure_runtime_dirs())
    if not deleted:
        raise HTTPException(status_code=404, detail="没有找到这个风格档案。")
    return {"ok": True}


@app.get("/product/capabilities", dependencies=[Depends(require_token)])
async def api_product_capabilities() -> dict[str, Any]:
    return {"capabilities": product_features.list_capabilities()}


@app.patch("/product/capabilities/{capability_id}", dependencies=[Depends(require_token)])
async def api_product_capability_update(capability_id: str, payload: CapabilityUpdateRequest) -> dict[str, Any]:
    capability = product_features.update_capability(capability_id, enabled=payload.enabled)
    if capability is None:
        raise HTTPException(status_code=404, detail="没有找到这个能力。")
    return {"capability": capability}


@app.get("/upstream/status", dependencies=[Depends(require_token)])
async def api_upstream_status() -> dict[str, Any]:
    return product_features.upstream_status()


@app.get("/usage/summary", dependencies=[Depends(require_token)])
async def api_usage_summary() -> dict[str, Any]:
    return product_features.usage_summary(ensure_runtime_dirs())


@app.get("/advanced/extensions", dependencies=[Depends(require_token)])
async def api_advanced_extensions() -> dict[str, Any]:
    return product_features.advanced_extensions(ensure_runtime_dirs())


@app.get("/advanced/config/export", dependencies=[Depends(require_token)])
async def api_advanced_config_export() -> dict[str, Any]:
    return product_features.advanced_config_export(ensure_runtime_dirs())


@app.post("/advanced/config/import", dependencies=[Depends(require_token)])
async def api_advanced_config_import(payload: AdvancedConfigImportRequest) -> dict[str, Any]:
    return product_features.advanced_config_import(payload.config, paths=ensure_runtime_dirs())


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
