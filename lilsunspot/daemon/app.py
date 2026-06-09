from __future__ import annotations

import platform
import os
import webbrowser
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lilsunspot import __version__

from .auth import load_or_create_token, require_token
from .chat_client import current_runtime_model, send_chat_message
from .config_paths import ensure_runtime_dirs
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
from .hermes_runtime import HermesRuntimeError, save_provider_credentials
from .logging_utils import configure_logging
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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Lilsunspot-Token"],
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


class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


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
    return {
        "ok": True,
        "provider": result["provider"],
        "model": result["model"],
        "hermes_home": str(ensure_runtime_dirs().hermes_home),
    }


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
    return await send_chat_message(payload.message, payload.conversation_id)


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
        return request_weixin_send_approval(payload.recipient, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/safety/policy", dependencies=[Depends(require_token)])
async def safety_policy() -> dict[str, Any]:
    return {"policy": load_safety_policy()}


@app.get("/safety/approvals", dependencies=[Depends(require_token)])
async def safety_approvals() -> dict[str, Any]:
    return list_pending_approvals()


@app.post("/safety/approvals/request", dependencies=[Depends(require_token)])
async def safety_approval_request(payload: ApprovalRequest) -> dict[str, Any]:
    try:
        return request_safety_approval(
            payload.operation,
            payload.summary or f"请求执行 {payload.operation}",
            payload.details,
            payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/safety/approvals/{approval_id}/decide", dependencies=[Depends(require_token)])
async def safety_approval_decide(approval_id: str, payload: ApprovalDecisionRequest) -> dict[str, Any]:
    try:
        return decide_approval(approval_id, payload.decision)
    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/safety/approvals/placeholder", dependencies=[Depends(require_token)])
async def safety_approval_placeholder(payload: ApprovalPlaceholderRequest) -> dict[str, Any]:
    return describe_approval_placeholder(payload.operation)


@app.get("/doctor/run", dependencies=[Depends(require_token)])
async def doctor_run() -> dict[str, Any]:
    return run_doctor_checks()


@app.post("/doctor/repair", dependencies=[Depends(require_token)])
async def doctor_repair(payload: RepairRequest) -> dict[str, Any]:
    return repair_placeholder(payload.check_name)


def main() -> None:
    import uvicorn

    uvicorn.run("lilsunspot.daemon.app:app", host=BIND_HOST, port=BIND_PORT, reload=False)


if __name__ == "__main__":
    main()
