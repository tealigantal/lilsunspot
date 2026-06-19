from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .prompt_compiler import compile_mode_prompt
from .providers import MODE_PROFILES_FILE, load_yaml_resource


MODE_STATE_FILE_NAME = "mode-profile.json"
MODE_METADATA_KEY = "mode_profile"
SLIDER_KEYS = ("style_axis", "detail_level", "autonomy_level")
DEFAULT_MODE_ID = "balanced"
CUSTOM_MODE_ID = "custom"
FIXED_PRESET_IDS = {"pragmatic", "balanced", "emotional"}
MODE_SCOPES = {"global", "conversation", "turn"}
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


def _normalize_mode_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    selected = str(payload.get("mode") or "").strip()
    if not selected:
        return None
    raw_sliders = payload.get("sliders") if isinstance(payload.get("sliders"), dict) else {}
    sliders: dict[str, int] = {}
    for key in SLIDER_KEYS:
        value = _coerce_slider(raw_sliders.get(key))
        if value is not None:
            sliders[key] = value
    result: dict[str, Any] = {"mode": selected}
    if sliders:
        result["sliders"] = sliders
    updated_at = str(payload.get("updated_at") or "").strip()
    if updated_at:
        result["updated_at"] = updated_at
    return result


def _read_global_mode_payload(paths: RuntimePaths) -> dict[str, Any]:
    state_path = _mode_state_path(paths)
    if state_path.exists():
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            normalized = _normalize_mode_payload(payload)
            if normalized is not None:
                return normalized
        except (OSError, json.JSONDecodeError):
            pass
    return {"mode": DEFAULT_MODE_ID}


def _write_global_mode_payload(paths: RuntimePaths, payload: dict[str, Any]) -> None:
    state_path = _mode_state_path(paths)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_path)


def _mode_from_payload(
    payload: dict[str, Any],
    *,
    scope: str,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    selected = str(payload.get("mode") or DEFAULT_MODE_ID).strip() or DEFAULT_MODE_ID
    raw_sliders = payload.get("sliders") if isinstance(payload.get("sliders"), dict) else {}
    sliders = {
        key: value
        for key in SLIDER_KEYS
        if (value := _coerce_slider(raw_sliders.get(key))) is not None
    }

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
    result: dict[str, Any] = {
        "current": profile["id"],
        "profile": profile,
        "prompt": prompt,
        "scope": scope,
    }
    if conversation_id:
        result["conversation_id"] = conversation_id
    return result


def _conversation_mode_payload(conversation_id: str, paths: RuntimePaths) -> dict[str, Any] | None:
    from . import conversations

    conversation = conversations.get_conversation(conversation_id, paths)
    metadata = conversation.get("metadata") if conversation and isinstance(conversation.get("metadata"), dict) else {}
    return _normalize_mode_payload(metadata.get(MODE_METADATA_KEY) if isinstance(metadata, dict) else None)


def get_current_mode(
    paths: RuntimePaths | None = None,
    *,
    conversation_id: str | None = None,
    turn_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    selected_payload = _read_global_mode_payload(paths)
    selected_scope = "global"
    resolved_conversation_id = (conversation_id or "").strip()

    if resolved_conversation_id:
        conversation_payload = _conversation_mode_payload(resolved_conversation_id, paths)
        if conversation_payload is not None:
            selected_payload = conversation_payload
            selected_scope = "conversation"

    turn_payload = _normalize_mode_payload(turn_override)
    if turn_payload is not None:
        selected_payload = turn_payload
        selected_scope = "turn"

    return _mode_from_payload(
        selected_payload,
        scope=selected_scope,
        conversation_id=resolved_conversation_id or None,
    )


def _selection_payload(
    mode: str,
    *,
    base_profile: dict[str, Any],
    style_axis: int | None = None,
    detail_level: int | None = None,
    autonomy_level: int | None = None,
) -> dict[str, Any]:
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
        current_defaults = _profile_defaults(base_profile)
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
    return payload


def _normalize_scope(scope: str | None, conversation_id: str | None) -> str:
    requested = (scope or "").strip().lower()
    if not requested:
        return "conversation" if (conversation_id or "").strip() else "global"
    if requested not in MODE_SCOPES:
        raise ValueError("输出模式作用域不正确。")
    if requested in {"conversation", "turn"} and not (conversation_id or "").strip():
        raise ValueError("请选择一个对话后再设置会话输出模式。")
    return requested


def select_mode(
    mode: str,
    paths: RuntimePaths | None = None,
    *,
    style_axis: int | None = None,
    detail_level: int | None = None,
    autonomy_level: int | None = None,
    conversation_id: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    paths = paths or ensure_runtime_dirs()
    resolved_conversation_id = (conversation_id or "").strip()
    resolved_scope = _normalize_scope(scope, resolved_conversation_id)
    base = get_current_mode(paths, conversation_id=resolved_conversation_id or None) if resolved_scope != "global" else get_current_mode(paths)
    payload = _selection_payload(
        mode,
        base_profile=base["profile"],
        style_axis=style_axis,
        detail_level=detail_level,
        autonomy_level=autonomy_level,
    )

    from . import conversations

    if resolved_scope == "global":
        _write_global_mode_payload(paths, payload)
        result = get_current_mode(paths)
    elif resolved_scope == "conversation":
        updated = conversations.update_conversation(
            resolved_conversation_id,
            metadata_patch={MODE_METADATA_KEY: payload},
            paths=paths,
        )
        if updated is None:
            raise ValueError("没有找到这个对话。")
        result = get_current_mode(paths, conversation_id=resolved_conversation_id)
    else:
        result = get_current_mode(paths, conversation_id=resolved_conversation_id, turn_override=payload)

    conversations.append_event(
        "mode.changed",
        {
            "mode": result,
            "conversation_id": resolved_conversation_id or None,
            "scope": result.get("scope"),
            "control_event": True,
        },
        paths=paths,
    )
    return result
