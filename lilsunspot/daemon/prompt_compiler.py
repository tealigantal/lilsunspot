from __future__ import annotations

from typing import Any

from .providers import MODE_PROMPT_FILE, load_yaml_resource


PROMPT_LAYER_IDS = ("mode_profile", "slider_overrides")


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _layer_label(config: dict[str, Any], layer_id: str, fallback: str) -> str:
    layers = config.get("layers") if isinstance(config.get("layers"), dict) else {}
    layer = layers.get(layer_id) if isinstance(layers.get(layer_id), dict) else {}
    return _as_text(layer.get("label")) or fallback


def _load_prompt_config() -> dict[str, Any]:
    data = load_yaml_resource(MODE_PROMPT_FILE)
    if not isinstance(data, dict):
        raise ValueError("default_mode_prompt.yaml must contain a mapping")
    return data


def slider_summary(profile: dict[str, Any]) -> str:
    style_axis = _as_int(profile.get("style_axis"))
    style = "表达更务实" if style_axis <= 35 else "表达更有陪伴感" if style_axis >= 70 else "表达平衡清楚"
    return f"{style}。回答长度、推理深度和行动次数由独立的生成控制决定。"


def compile_mode_prompt(profile: dict[str, Any]) -> dict[str, Any]:
    config = _load_prompt_config()
    mode_hint = _as_text(profile.get("system_hint"))
    mode_summary = _as_text(profile.get("description")) or f"使用 {profile.get('id', 'balanced')} 表达风格。"
    current_slider_summary = slider_summary(profile)

    system_hint = "\n\n".join(
        item
        for item in (
            f"当前表达风格：{_as_text(profile.get('id')) or 'balanced'}。\n{mode_hint}",
            f"当前措辞偏好：{current_slider_summary}",
        )
        if item.strip()
    )

    return {
        "system_hint": system_hint,
        "layers": [
            {
                "id": "mode_profile",
                "label": _layer_label(config, "mode_profile", "表达风格预设"),
                "summary": mode_summary,
            },
            {
                "id": "slider_overrides",
                "label": _layer_label(config, "slider_overrides", "表达滑杆覆盖"),
                "summary": current_slider_summary,
            },
        ],
        "slider_summary": current_slider_summary,
    }
