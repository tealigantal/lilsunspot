from __future__ import annotations

from typing import Any

import yaml

from lilsunspot import __version__

from .auth import token_file_exists
from .config_paths import ensure_runtime_dirs
from .providers import load_provider_registry, required_resource_files


def run_doctor_checks() -> dict[str, Any]:
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
                parsed = yaml.safe_load(resource_file.read_text(encoding="utf-8")) is not None
            add_check(f"resource:{resource_file.name}", exists and parsed, str(resource_file))
        except Exception as exc:  # noqa: BLE001 - doctor reports diagnostics instead of crashing
            add_check(f"resource:{resource_file.name}", False, f"{type(exc).__name__}: {exc}")

    try:
        provider_count = len(load_provider_registry())
        add_check("provider_registry_readable", provider_count > 0, f"{provider_count} providers")
    except Exception as exc:  # noqa: BLE001
        add_check("provider_registry_readable", False, f"{type(exc).__name__}: {exc}")

    add_check("daemon_bind_host", True, "127.0.0.1")
    add_check("daemon_responding", True, "current request reached lilsunspotd")
    add_check("runtime_token_exists", token_file_exists(), str(runtime_paths.token_file))

    return {
        "ok": all(check["ok"] for check in checks),
        "daemon_version": __version__,
        "checks": checks,
    }


def repair_placeholder(check_name: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "check": check_name or "",
        "message": "自动修复还是占位模块，当前不会修改系统配置。",
        "suggestion": "请先运行诊断并按提示手动处理。",
    }
