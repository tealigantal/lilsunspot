from __future__ import annotations

from typing import Any

from .providers import MODE_PROMPT_FILE, load_yaml_resource


PROMPT_LAYER_IDS = ("product_baseline", "mode_profile", "slider_overrides")


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
    baseline = data.get("product_baseline")
    if not isinstance(baseline, dict) or not _as_text(baseline.get("system_hint")):
        raise ValueError("default_mode_prompt.yaml must contain product_baseline.system_hint")
    return data


def slider_summary(profile: dict[str, Any]) -> str:
    style_axis = _as_int(profile.get("style_axis"))
    detail_level = _as_int(profile.get("detail_level"))
    autonomy_level = _as_int(profile.get("autonomy_level"))

    style = "表达更务实" if style_axis <= 35 else "表达更有陪伴感" if style_axis >= 70 else "表达平衡清楚"
    detail = "回答保持简短" if detail_level <= 35 else "回答给出更充分细节" if detail_level >= 70 else "回答详略适中"
    autonomy = (
        "风险或不确定时优先确认"
        if autonomy_level <= 35
        else "可自动推进明确的下一步"
        if autonomy_level >= 70
        else "在自动推进和必要确认之间保持平衡"
    )
    return f"{style}；{detail}；{autonomy}。"


def compile_mode_prompt(profile: dict[str, Any]) -> dict[str, Any]:
    config = _load_prompt_config()
    baseline = config["product_baseline"]
    baseline_hint = _as_text(baseline.get("system_hint"))
    baseline_summary = _as_text(baseline.get("summary"))
    mode_hint = _as_text(profile.get("system_hint"))
    mode_summary = _as_text(profile.get("description")) or f"使用 {profile.get('id', 'default')} 输出模式。"
    current_slider_summary = slider_summary(profile)

    system_hint = "\n\n".join(
        item
        for item in (
            baseline_hint,
            f"当前输出模式：{_as_text(profile.get('id')) or 'default'}。\n{mode_hint}",
            f"当前输出偏好：{current_slider_summary}",
        )
        if item.strip()
    )

    return {
        "system_hint": system_hint,
        "layers": [
            {
                "id": "product_baseline",
                "label": _layer_label(config, "product_baseline", "产品基线"),
                "summary": baseline_summary,
            },
            {
                "id": "mode_profile",
                "label": _layer_label(config, "mode_profile", "模式预设"),
                "summary": mode_summary,
            },
            {
                "id": "slider_overrides",
                "label": _layer_label(config, "slider_overrides", "三滑杆覆盖"),
                "summary": current_slider_summary,
            },
        ],
        "slider_summary": current_slider_summary,
    }
