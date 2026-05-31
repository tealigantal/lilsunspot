from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs


RUNTIME_DESCRIPTOR_TYPE = "lilsunspot-daemon-runtime"
RUNTIME_DESCRIPTOR_VERSION = 1


def base_url_for(host: str, port: int) -> str:
    if host != "127.0.0.1":
        raise ValueError("lilsunspotd 只能绑定到 127.0.0.1。")
    if port < 1 or port > 65535:
        raise ValueError("lilsunspotd 端口不正确。")
    return f"http://{host}:{port}"


def build_runtime_descriptor(
    host: str,
    port: int,
    paths: RuntimePaths | None = None,
    *,
    pid: int | None = None,
) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    return {
        "type": RUNTIME_DESCRIPTOR_TYPE,
        "version": RUNTIME_DESCRIPTOR_VERSION,
        "base_url": base_url_for(host, port),
        "host": host,
        "port": port,
        "pid": pid if pid is not None else os.getpid(),
        "data_dir": str(runtime_paths.data_dir),
        "token_file": str(runtime_paths.token_file),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def write_runtime_descriptor(
    host: str,
    port: int,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    payload = build_runtime_descriptor(host, port, runtime_paths)
    tmp = runtime_paths.runtime_file.with_suffix(runtime_paths.runtime_file.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(runtime_paths.runtime_file)
    try:
        runtime_paths.runtime_file.chmod(0o600)
    except OSError:
        pass
    return payload


def read_runtime_descriptor(paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    runtime_paths = paths or ensure_runtime_dirs()
    if not runtime_paths.runtime_file.exists():
        return None
    try:
        payload = json.loads(runtime_paths.runtime_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != RUNTIME_DESCRIPTOR_TYPE:
        return None
    return payload
