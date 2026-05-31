from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .providers import MODE_PROFILES_FILE, load_yaml_resource


MODE_STATE_FILE_NAME = "mode-profile.json"


def load_mode_profiles() -> list[dict[str, Any]]:
    data = load_yaml_resource(MODE_PROFILES_FILE)
    modes = data.get("modes") if isinstance(data, dict) else None
    if not isinstance(modes, dict):
        raise ValueError("default_mode_profiles.yaml must contain a modes mapping")
    return [{"id": str(mode_id), **dict(profile)} for mode_id, profile in modes.items() if isinstance(profile, dict)]


def _mode_state_path(paths: RuntimePaths) -> Path:
    return paths.data_dir / MODE_STATE_FILE_NAME


def get_current_mode(paths: RuntimePaths | None = None) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    selected = "default"
    state_path = _mode_state_path(paths)
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            selected = str(payload.get("mode") or selected)
        except (OSError, json.JSONDecodeError):
            selected = "default"

    profiles = load_mode_profiles()
    profile = next((item for item in profiles if item["id"] == selected), None) or profiles[0]
    return {"current": profile["id"], "profile": profile}


def select_mode(mode: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    mode = mode.strip()
    profiles = load_mode_profiles()
    if not any(item["id"] == mode for item in profiles):
        raise ValueError("没有找到这个输出模式。")
    payload = {"mode": mode, "updated_at": datetime.now(timezone.utc).isoformat()}
    state_path = _mode_state_path(paths)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path)
    return get_current_mode(paths)
