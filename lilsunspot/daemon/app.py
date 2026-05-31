from __future__ import annotations

import platform
import webbrowser
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lilsunspot import __version__

from .auth import load_or_create_token, require_token
from .chat_client import current_runtime_model, send_chat_message
from .config_paths import ensure_runtime_dirs
from .doctor import repair_placeholder, run_doctor_checks
from .gateway import weixin_commands, weixin_status
from .hermes_runtime import HermesRuntimeError, save_provider_credentials
from .logging_utils import configure_logging
from .modes import get_current_mode, load_mode_profiles, select_mode
from .provider_client import test_provider_connection
from .providers import load_provider_registry, provider_by_id
from .safety import describe_approval_placeholder, list_pending_approvals, load_safety_policy


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

paths = ensure_runtime_dirs()
logger = configure_logging(paths.logs_dir)
load_or_create_token()

app = FastAPI(
    title="lilsunspotd",
    version=__version__,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
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


class OpenKeyUrlRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    open_browser: bool = False


class SaveProviderRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    api_key: str = ""


class ProviderTestRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str | None = None
    api_key: str = ""


class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


class SelectModeRequest(BaseModel):
    mode: str = Field(..., min_length=1)


class ApprovalPlaceholderRequest(BaseModel):
    operation: str = Field(..., min_length=1)


class RepairRequest(BaseModel):
    check_name: str | None = None


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


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
        "bind_host": DEFAULT_HOST,
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
            "message": "没有找到这个模型服务商。",
            "suggestion": "请重新选择服务商。",
        }
    return await test_provider_connection(provider, payload.model, payload.api_key)


@app.post("/providers/save", dependencies=[Depends(require_token)])
async def save_provider(payload: SaveProviderRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="没有找到这个模型服务商。")
    try:
        result = save_provider_credentials(provider, payload.model, payload.api_key)
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
        return select_mode(payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chat/send", dependencies=[Depends(require_token)])
async def chat_send(payload: ChatSendRequest) -> dict[str, Any]:
    return await send_chat_message(payload.message, payload.conversation_id)


@app.get("/gateway/weixin/status", dependencies=[Depends(require_token)])
async def gateway_weixin_status() -> dict[str, Any]:
    return weixin_status()


@app.get("/gateway/weixin/commands", dependencies=[Depends(require_token)])
async def gateway_weixin_commands() -> dict[str, Any]:
    return weixin_commands()


@app.get("/safety/policy", dependencies=[Depends(require_token)])
async def safety_policy() -> dict[str, Any]:
    return {"policy": load_safety_policy()}


@app.get("/safety/approvals", dependencies=[Depends(require_token)])
async def safety_approvals() -> dict[str, Any]:
    return list_pending_approvals()


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

    uvicorn.run("lilsunspot.daemon.app:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    main()
