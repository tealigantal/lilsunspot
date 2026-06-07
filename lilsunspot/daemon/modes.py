from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .providers import MODE_PROFILES_FILE, load_yaml_resource


MODE_STATE_FILE_NAME = "mode-profile.json"
SLIDER_KEYS = ("style_axis", "detail_level", "autonomy_level")


def load_mode_profiles() -> list[dict[str, Any]]:
    data = load_yaml_resource(MODE_PROFILES_FILE)
    modes = data.get("modes") if isinstance(data, dict) else None
    if not isinstance(modes, dict):
        raise ValueError("default_mode_profiles.yaml must contain a modes mapping")
    return [{"id": str(mode_id), **dict(profile)} for mode_id, profile in modes.items() if isinstance(profile, dict)]


def _mode_state_path(paths: RuntimePaths) -> Path:
    return paths.data_dir / MODE_STATE_FILE_NAME


def _coerce_slider(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, number))


def _slider_hint(profile: dict[str, Any]) -> str:
    style_axis = int(profile.get("style_axis") or 0)
    detail_level = int(profile.get("detail_level") or 0)
    autonomy_level = int(profile.get("autonomy_level") or 0)

    style = "表达更务实" if style_axis <= 35 else "表达更有陪伴感" if style_axis >= 70 else "表达平衡清楚"
    detail = "回答保持简短" if detail_level <= 35 else "回答给出更充分细节" if detail_level >= 70 else "回答详略适中"
    autonomy = "风险或不确定时优先确认" if autonomy_level <= 35 else "可自动推进明确的下一步" if autonomy_level >= 70 else "在自动推进和必要确认之间保持平衡"
    return f"{style}；{detail}；{autonomy}。"


def get_current_mode(paths: RuntimePaths | None = None) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    selected = "default"
    sliders: dict[str, int] = {}
    state_path = _mode_state_path(paths)
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            selected = str(payload.get("mode") or selected)
            raw_sliders = payload.get("sliders") if isinstance(payload.get("sliders"), dict) else {}
            sliders = {
                key: value
                for key in SLIDER_KEYS
                if (value := _coerce_slider(raw_sliders.get(key))) is not None
            }
        except (OSError, json.JSONDecodeError):
            selected = "default"

    profiles = load_mode_profiles()
    profile = dict(next((item for item in profiles if item["id"] == selected), None) or profiles[0])
    if sliders:
        profile.update(sliders)
        base_hint = str(profile.get("system_hint") or "").strip()
        profile["system_hint"] = f"{base_hint}\n当前输出偏好：{_slider_hint(profile)}".strip()
    return {"current": profile["id"], "profile": profile}


def select_mode(
    mode: str,
    paths: RuntimePaths | None = None,
    *,
    style_axis: int | None = None,
    detail_level: int | None = None,
    autonomy_level: int | None = None,
) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    mode = mode.strip()
    profiles = load_mode_profiles()
    if not any(item["id"] == mode for item in profiles):
        raise ValueError("没有找到这个输出模式。")
    sliders = {
        key: value
        for key, raw in {
            "style_axis": style_axis,
            "detail_level": detail_level,
            "autonomy_level": autonomy_level,
        }.items()
        if (value := _coerce_slider(raw)) is not None
    }
    payload: dict[str, Any] = {"mode": mode, "updated_at": datetime.now(timezone.utc).isoformat()}
    if sliders:
        payload["sliders"] = sliders
    state_path = _mode_state_path(paths)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path)
    return get_current_mode(paths)
