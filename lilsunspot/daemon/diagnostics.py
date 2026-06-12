from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lilsunspot import __version__

from .audit import list_audit_events, record_audit_event, redact_value
from .capabilities import list_capabilities
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .doctor import run_doctor_checks
from .hermes_compat import audit_hermes_compatibility
from .hermes_runtime import model_runtime_config, read_hermes_config


DIAGNOSTICS_DIR_NAME = "diagnostics"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _write_json_to_zip(zf: zipfile.ZipFile, name: str, payload: Any) -> None:
    zf.writestr(
        name,
        json.dumps(redact_value(payload), ensure_ascii=False, indent=2, sort_keys=True),
    )


def _safe_log_summary(paths: RuntimePaths) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(paths.logs_dir.glob("*.log"))[-5:]:
        try:
            stat = path.stat()
        except OSError:
            continue
        summaries.append(
            {
                "file": path.name,
                "size_bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return summaries


def export_diagnostics(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    diagnostics_dir = runtime_paths.data_dir / DIAGNOSTICS_DIR_NAME
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_id = f"diagnostics-{_now_stamp()}"
    archive_path = diagnostics_dir / f"{diagnostic_id}.zip"

    doctor = run_doctor_checks()
    capabilities = list_capabilities(runtime_paths)
    compatibility = audit_hermes_compatibility()
    audit = list_audit_events(limit=100, paths=runtime_paths)
    config = read_hermes_config(runtime_paths)

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_json_to_zip(
            zf,
            "summary.json",
            {
                "product": "lilsunspot",
                "version": __version__,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "data_dir_name": runtime_paths.data_dir.name,
                "hermes_home_name": runtime_paths.hermes_home.name,
            },
        )
        _write_json_to_zip(zf, "doctor.json", doctor)
        _write_json_to_zip(zf, "capabilities.json", capabilities)
        _write_json_to_zip(zf, "model_runtime.json", model_runtime_config(runtime_paths))
        _write_json_to_zip(zf, "hermes_compatibility.json", compatibility)
        _write_json_to_zip(zf, "audit_events.json", audit)
        _write_json_to_zip(zf, "config_shape.json", _config_shape(config))
        _write_json_to_zip(zf, "logs_summary.json", _safe_log_summary(runtime_paths))

    event = record_audit_event(
        "diagnostics_export",
        "导出了脱敏诊断包。",
        source="doctor",
        details={"diagnostic_id": diagnostic_id, "file_name": archive_path.name, "size_bytes": archive_path.stat().st_size},
        paths=runtime_paths,
    )
    return {
        "ok": True,
        "diagnostic_id": diagnostic_id,
        "file_name": archive_path.name,
        "size_bytes": archive_path.stat().st_size,
        "message": "脱敏诊断包已导出到本机数据目录。",
        "audit_event": event,
    }


def _config_shape(value: Any) -> Any:
    if isinstance(value, dict):
        shaped: dict[str, Any] = {}
        for key, child in value.items():
            if isinstance(child, dict):
                shaped[str(key)] = _config_shape(child)
            elif isinstance(child, list):
                shaped[str(key)] = [{"type": type(item).__name__} for item in child[:20]]
            elif child in ("", None):
                shaped[str(key)] = child
            else:
                shaped[str(key)] = f"<{type(child).__name__}>"
        return shaped
    return f"<{type(value).__name__}>"
