from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .prompt_compiler import compile_mode_prompt
from .providers import MODE_PROFILES_FILE, load_yaml_resource


MODE_STATE_FILE_NAME = "mode-profile.json"
SLIDER_KEYS = ("style_axis", "detail_level", "autonomy_level")
DEFAULT_MODE_ID = "balanced"
CUSTOM_MODE_ID = "custom"
FIXED_PRESET_IDS = {"pragmatic", "balanced", "emotional"}
MODE_LABELS = {
    "pragmatic": "务实",
    "balanced": "均衡",
    "emotional": "感性",
    "custom": "自定义",
}


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


def _profile_slider_default(profile: dict[str, Any], key: str) -> int:
    return _coerce_slider(profile.get(key)) or 0


def _profile_defaults(profile: dict[str, Any]) -> dict[str, int]:
    return {key: _profile_slider_default(profile, key) for key in SLIDER_KEYS}


def _profile_by_id(profiles: list[dict[str, Any]], mode_id: str) -> dict[str, Any] | None:
    return next((item for item in profiles if item["id"] == mode_id), None)


def _complete_sliders(base: dict[str, int], overrides: dict[str, int]) -> dict[str, int]:
    return {key: overrides.get(key, base.get(key, 0)) for key in SLIDER_KEYS}


def _sliders_match(left: dict[str, int], right: dict[str, int]) -> bool:
    return all(left.get(key) == right.get(key) for key in SLIDER_KEYS)


def get_current_mode(paths: RuntimePaths | None = None) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    selected = DEFAULT_MODE_ID
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
            selected = DEFAULT_MODE_ID

    profiles = load_mode_profiles()
    profile = _profile_by_id(profiles, selected)
    if profile is None:
        selected = CUSTOM_MODE_ID if sliders else DEFAULT_MODE_ID
        profile = _profile_by_id(profiles, selected) or _profile_by_id(profiles, DEFAULT_MODE_ID) or profiles[0]

    profile = dict(profile)
    defaults = _profile_defaults(profile)
    completed_sliders = _complete_sliders(defaults, sliders)
    if selected in FIXED_PRESET_IDS and sliders and not _sliders_match(completed_sliders, defaults):
        selected = CUSTOM_MODE_ID
        profile = dict(_profile_by_id(profiles, CUSTOM_MODE_ID) or profile)
        completed_sliders = _complete_sliders(_profile_defaults(profile), sliders)

    profile["id"] = selected
    for key, value in completed_sliders.items():
        profile[key] = value
    prompt = compile_mode_prompt(profile)
    profile["system_hint"] = prompt["system_hint"]
    return {"current": profile["id"], "profile": profile, "prompt": prompt}


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
    requested_profile = _profile_by_id(profiles, mode)
    if requested_profile is None:
        raise ValueError("没有找到这个输出模式。")
    supplied_sliders = {
        key: value
        for key, raw in {
            "style_axis": style_axis,
            "detail_level": detail_level,
            "autonomy_level": autonomy_level,
        }.items()
        if (value := _coerce_slider(raw)) is not None
    }
    selected = mode
    requested_defaults = _profile_defaults(requested_profile)
    saved_sliders: dict[str, int] = {}

    if mode == CUSTOM_MODE_ID:
        current_profile = get_current_mode(paths).get("profile")
        current_defaults = (
            _profile_defaults(current_profile)
            if isinstance(current_profile, dict)
            else _profile_defaults(requested_profile)
        )
        saved_sliders = _complete_sliders(current_defaults, supplied_sliders)
    elif mode in FIXED_PRESET_IDS:
        completed = _complete_sliders(requested_defaults, supplied_sliders)
        if supplied_sliders and not _sliders_match(completed, requested_defaults):
            selected = CUSTOM_MODE_ID
            saved_sliders = completed
    else:
        saved_sliders = _complete_sliders(requested_defaults, supplied_sliders)

    payload: dict[str, Any] = {"mode": selected, "updated_at": datetime.now(timezone.utc).isoformat()}
    if selected == CUSTOM_MODE_ID or saved_sliders:
        payload["sliders"] = saved_sliders
    state_path = _mode_state_path(paths)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path)
    result = get_current_mode(paths)
    from . import conversations

    label = MODE_LABELS.get(str(result.get("current") or mode), mode)
    message = conversations.create_system_message(
        f"已把回答风格调成：{label}",
        metadata={"kind": "mode.changed", "mode": result.get("current")},
        paths=paths,
    )
    conversations.append_event(
        "mode.changed",
        {"mode": result, "message": message},
        paths=paths,
    )
    return result
