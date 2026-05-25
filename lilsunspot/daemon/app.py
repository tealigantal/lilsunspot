from __future__ import annotations

import platform
import webbrowser
from typing import Any

import yaml
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lilsunspot import __version__

from .auth import load_or_create_token, require_token, token_file_exists
from .config_paths import ensure_runtime_dirs
from .hermes_runtime import (
    HermesRuntimeError,
    read_current_provider,
    save_provider_credentials,
)
from .logging_utils import configure_logging, mask_secret, redact_text
from .providers import (
    load_provider_registry,
    provider_by_id,
    public_provider,
    public_provider_registry,
    required_resource_files,
    test_provider_connection,
    validate_key_format,
)


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


class ValidateKeyFormatRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    api_key: str = ""


class ProviderTestRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    api_key: str = ""
    model: str | None = None


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
    return {"providers": public_provider_registry()}


@app.get("/providers/current", dependencies=[Depends(require_token)])
async def providers_current() -> dict[str, Any]:
    return read_current_provider(load_provider_registry())


@app.post("/providers/open-key-url", dependencies=[Depends(require_token)])
async def open_key_url(payload: OpenKeyUrlRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider}' is not configured.")
    key_url = str(provider.get("key_url") or provider.get("detect_url") or "").strip()
    if not key_url:
        raise HTTPException(status_code=400, detail="This provider has no key URL configured.")
    opened = False
    if payload.open_browser:
        try:
            opened = bool(webbrowser.open(key_url))
        except Exception:  # noqa: BLE001 - return a user-facing result instead of a stack trace
            return {
                "provider": str(provider["id"]),
                "key_url": key_url,
                "opened": False,
                "error": "Could not open the browser automatically. Use the key_url manually.",
            }
    return {"provider": str(provider["id"]), "key_url": key_url, "opened": opened}


@app.post("/providers/validate-key-format", dependencies=[Depends(require_token)])
async def provider_validate_key_format(payload: ValidateKeyFormatRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider}' is not configured.")
    ok, reason = validate_key_format(provider, payload.api_key)
    return {"ok": ok, "provider": str(provider["id"]), "reason": reason}


@app.post("/providers/test", dependencies=[Depends(require_token)])
async def provider_test(payload: ProviderTestRequest) -> dict[str, Any]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider}' is not configured.")
    result = await test_provider_connection(provider, payload.api_key, payload.model)
    if "message" in result:
        result["message"] = redact_text(result["message"])
    return result


@app.post("/providers/save", dependencies=[Depends(require_token)])
async def save_provider(payload: SaveProviderRequest) -> dict[str, str | bool]:
    provider = provider_by_id(payload.provider)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider}' is not configured.")
    try:
        result = save_provider_credentials(provider, payload.model, payload.api_key)
    except HermesRuntimeError as exc:
        raise HTTPException(status_code=400, detail=redact_text(exc)) from exc
    logger.info(
        "provider saved provider=%s model=%s key=%s",
        result["provider"],
        result["model"],
        mask_secret(payload.api_key),
    )
    return {
        "ok": True,
        "provider": str(result["provider"]),
        "model": str(result["model"]),
        "env_written": bool(result["env_written"]),
        "config_written": bool(result["config_written"]),
    }


@app.get("/providers/{provider_id}", dependencies=[Depends(require_token)])
async def provider_detail(provider_id: str) -> dict[str, Any]:
    provider = provider_by_id(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' is not configured.")
    return public_provider(provider)


def _doctor_check(
    checks: list[dict[str, Any]],
    check_id: str,
    ok: bool,
    severity: str,
    message: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "ok": ok,
            "severity": severity,
            "message": message,
        }
    )


def _parse_yaml_file(path: Any) -> tuple[bool, str]:
    try:
        if not path.exists():
            return False, f"{path} does not exist."
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        if parsed is None:
            return False, f"{path} is empty."
        return True, f"{path} is present and parseable."
    except Exception as exc:  # noqa: BLE001 - doctor converts diagnostics to structured checks
        return False, redact_text(f"{type(exc).__name__}: {exc}")


def _doctor_payload() -> dict[str, Any]:
    runtime_paths = ensure_runtime_dirs()
    checks: list[dict[str, Any]] = []

    _doctor_check(
        checks,
        "data_dir_exists",
        runtime_paths.data_dir.exists(),
        "error",
        str(runtime_paths.data_dir),
    )
    _doctor_check(
        checks,
        "hermes_home_exists",
        runtime_paths.hermes_home.exists(),
        "error",
        str(runtime_paths.hermes_home),
    )
    _doctor_check(
        checks,
        "logs_dir_exists",
        runtime_paths.logs_dir.exists(),
        "error",
        str(runtime_paths.logs_dir),
    )
    _doctor_check(
        checks,
        "runtime_token_exists",
        token_file_exists(),
        "error",
        str(runtime_paths.token_file),
    )

    for resource_file in required_resource_files():
        ok, message = _parse_yaml_file(resource_file)
        _doctor_check(
            checks,
            f"resource:{resource_file.name}",
            ok,
            "error",
            message,
        )

    env_path = runtime_paths.hermes_home / ".env"
    config_path = runtime_paths.hermes_home / "config.yaml"
    _doctor_check(
        checks,
        "hermes_env_exists",
        env_path.exists(),
        "warning",
        str(env_path),
    )
    config_ok, config_message = _parse_yaml_file(config_path) if config_path.exists() else (
        False,
        f"{config_path} does not exist.",
    )
    _doctor_check(
        checks,
        "hermes_config_parseable",
        config_ok,
        "warning",
        config_message,
    )

    try:
        current = read_current_provider(load_provider_registry(), runtime_paths)
        provider_ok = bool(current.get("provider"))
        key_ok = bool(current.get("key_configured"))
        _doctor_check(
            checks,
            "current_provider_configured",
            provider_ok,
            "warning",
            f"Current provider: {current.get('provider') or 'not configured'}",
        )
        _doctor_check(
            checks,
            "current_provider_key_configured",
            key_ok,
            "warning",
            "Current provider key is configured." if key_ok else "Current provider key is not configured.",
        )
    except Exception as exc:  # noqa: BLE001 - keep doctor structured
        _doctor_check(
            checks,
            "current_provider_readable",
            False,
            "warning",
            redact_text(f"{type(exc).__name__}: {exc}"),
        )

    ok = all(check["ok"] or check["severity"] != "error" for check in checks)
    return {
        "ok": ok,
        "daemon_version": __version__,
        "checks": checks,
    }


@app.get("/doctor/run", dependencies=[Depends(require_token)])
@app.post("/doctor/run", dependencies=[Depends(require_token)])
async def doctor_run() -> dict[str, Any]:
    return _doctor_payload()


def main() -> None:
    import uvicorn

    uvicorn.run("lilsunspot.daemon.app:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    main()
