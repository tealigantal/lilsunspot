from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
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


def process_metadata() -> dict[str, Any]:
    packaged = bool(getattr(sys, "frozen", False))
    pyinstaller = packaged and hasattr(sys, "_MEIPASS")
    packager = "pyinstaller" if pyinstaller else ""
    process_model = "python_process"
    note_cn = "开发环境本地服务通常只有一个 Python 进程。"
    if pyinstaller:
        executable_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(str(getattr(sys, "_MEIPASS", ""))).resolve()
        if bundle_dir == executable_dir or executable_dir in bundle_dir.parents:
            process_model = "pyinstaller_onedir_single_process"
            if sys.platform == "darwin":
                note_cn = "安装版本地服务使用 PyInstaller onedir 打包，活动监视器里通常只会看到一个 lilsunspotd 服务进程。"
            else:
                note_cn = "安装版本地服务使用 PyInstaller onedir 打包，任务管理器里通常只会看到一个 lilsunspotd.exe 服务进程。"
        else:
            process_model = "pyinstaller_onefile_parent_child"
            note_cn = (
                "安装版本地服务使用 PyInstaller onefile 打包，Windows 任务管理器里可能同时看到父进程和服务子进程；"
                "runtime pid 是实际监听 127.0.0.1 端口的服务进程。"
            )
    return {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "executable": sys.executable,
        "packaged": packaged,
        "packager": packager,
        "process_model": process_model,
        "note_cn": note_cn,
    }


def build_runtime_descriptor(
    host: str,
    port: int,
    paths: RuntimePaths | None = None,
    *,
    pid: int | None = None,
) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    process = process_metadata()
    if pid is not None:
        process = {**process, "pid": pid}
    return {
        "type": RUNTIME_DESCRIPTOR_TYPE,
        "version": RUNTIME_DESCRIPTOR_VERSION,
        "base_url": base_url_for(host, port),
        "host": host,
        "port": port,
        "pid": process["pid"],
        "process": process,
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
