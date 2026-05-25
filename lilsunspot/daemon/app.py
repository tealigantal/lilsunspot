from __future__ import annotations

import platform
import webbrowser
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lilsunspot import __version__

from .auth import load_or_create_token, require_token, token_file_exists
from .config_paths import ensure_runtime_dirs
from .hermes_runtime import HermesRuntimeError, save_provider_credentials
from .logging_utils import configure_logging
from .providers import load_provider_registry, provider_by_id, required_resource_files


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

paths = ensure_runtime_dirs()
logger = configure_logging(paths.logs_dir)
load_or_create_token()

app = FastAPI(title="lilsunspotd", version=__version__)
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
    api_key: str = Field(..., min_length=1)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/runtime/info", dependencies=[Depends(require_token)])
async def runtime_info() -> dict[str, str]:
    runtime_paths = ensure_runtime_dirs()
    return {
        "data_dir": str(runtime_paths.data_dir),
        "hermes_home": str(runtime_paths.hermes_home),
        "logs_dir": str(runtime_paths.logs_dir),
        "platform": platform.platform(),
        "daemon_version": __version__,
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


@app.get("/doctor/run", dependencies=[Depends(require_token)])
async def doctor_run() -> dict[str, Any]:
    runtime_paths = ensure_runtime_dirs()
    checks: list[dict[str, Any]] = []

    def add_check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add_check("data_dir_exists", runtime_paths.data_dir.exists(), str(runtime_paths.data_dir))
    add_check("hermes_home_exists", runtime_paths.hermes_home.exists(), str(runtime_paths.hermes_home))
    add_check("logs_dir_exists", runtime_paths.logs_dir.exists(), str(runtime_paths.logs_dir))

    for resource_file in required_resource_files():
        try:
            exists = resource_file.exists()
            parsed = False
            if exists:
                import yaml

                parsed = yaml.safe_load(resource_file.read_text(encoding="utf-8")) is not None
            add_check(f"resource:{resource_file.name}", exists and parsed, str(resource_file))
        except Exception as exc:  # noqa: BLE001 - doctor reports diagnostics instead of crashing
            add_check(f"resource:{resource_file.name}", False, f"{type(exc).__name__}: {exc}")

    try:
        provider_count = len(load_provider_registry())
        add_check("provider_registry_readable", provider_count > 0, f"{provider_count} providers")
    except Exception as exc:  # noqa: BLE001
        add_check("provider_registry_readable", False, f"{type(exc).__name__}: {exc}")

    add_check("daemon_responding", True, "current request reached lilsunspotd")
    add_check("runtime_token_exists", token_file_exists(), str(runtime_paths.token_file))

    return {
        "ok": all(check["ok"] for check in checks),
        "daemon_version": __version__,
        "checks": checks,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("lilsunspot.daemon.app:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    main()
