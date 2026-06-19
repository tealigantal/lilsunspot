from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .modes import CUSTOM_MODE_ID, DEFAULT_MODE_ID, get_current_mode, load_mode_profiles, select_mode


MODE_INTENT_MAX_INPUT_CHARS = 80
SLIDER_KEYS = {"detail_level", "autonomy_level"}

MODE_LABELS = {
    "pragmatic": "务实",
    "balanced": "均衡",
    "emotional": "感性",
    "custom": "自定义",
}

MODE_ALIASES: dict[str, tuple[str, ...]] = {
    "pragmatic": ("pragmatic", "务实", "理性", "冷静", "直接"),
    "balanced": ("balanced", "均衡", "平衡"),
    "emotional": ("emotional", "感性", "温柔", "陪伴"),
    "custom": ("custom", "自定义"),
}

MODE_SWITCH_MARKERS = (
    "切换到",
    "切换成",
    "切换为",
    "切到",
    "调成",
    "调到",
    "调为",
    "改成",
    "换成",
    "设成",
    "设为",
    "设置成",
    "设置为",
)
MODE_QUERY_TEXTS = {
    "当前是什么模式",
    "当前是什么风格",
    "现在是什么模式",
    "现在是什么风格",
    "目前是什么模式",
    "目前是什么风格",
    "我现在是什么模式",
    "我现在是什么风格",
}
DETAIL_MORE_TEXTS = (
    "回答再详细一点",
    "回复再详细一点",
    "回答详细一点",
    "回复详细一点",
    "讲详细一点",
    "说详细一点",
    "解释详细一点",
    "更详细一点",
    "详细一点",
)
DETAIL_LESS_TEXTS = (
    "回答再简短一点",
    "回复再简短一点",
    "回答简短一点",
    "回复简短一点",
    "更简短一点",
    "简短一点",
    "短一点",
    "精简一点",
)
AUTONOMY_MORE_TEXTS = (
    "以后主动一点",
    "接下来主动一点",
    "更主动一点",
    "主动一点",
    "更主动",
    "主动推进",
    "自动推进",
)
AUTONOMY_LESS_TEXTS = (
    "以后谨慎一点",
    "接下来谨慎一点",
    "更谨慎一点",
    "谨慎一点",
    "多确认一点",
    "先确认",
    "不要擅自",
    "别擅自",
)


@dataclass(frozen=True)
class ModeIntent:
    kind: str
    mode: str | None = None
    slider: str | None = None
    delta: int = 0


def _is_short_local_candidate(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    if "\n" in value or "\r" in value:
        return False
    return len(value) <= MODE_INTENT_MAX_INPUT_CHARS


def _mode_from_text(text: str) -> str | None:
    value = text.strip().lower()
    for mode_id, aliases in MODE_ALIASES.items():
        if any(alias in value for alias in aliases):
            return mode_id
    return None


def _slash_mode_intent(text: str) -> ModeIntent | None:
    value = text.strip()
    if not value.lower().startswith("/mode"):
        return None
    parts = value.split()
    if len(parts) == 1:
        return ModeIntent(kind="query")
    mode = _mode_from_text(" ".join(parts[1:]))
    return ModeIntent(kind="mode", mode=mode) if mode else None


def _deterministic_mode_intent(text: str) -> ModeIntent | None:
    value = text.strip()
    if not _is_short_local_candidate(value):
        return None

    slash = _slash_mode_intent(value)
    if slash is not None:
        return slash

    compact = "".join(value.split())
    if compact in MODE_QUERY_TEXTS:
        return ModeIntent(kind="query")

    if any(marker in compact for marker in MODE_SWITCH_MARKERS):
        mode = _mode_from_text(compact)
        if mode:
            return ModeIntent(kind="mode", mode=mode)

    if compact in DETAIL_MORE_TEXTS:
        return ModeIntent(kind="slider", slider="detail_level", delta=20)
    if compact in DETAIL_LESS_TEXTS:
        return ModeIntent(kind="slider", slider="detail_level", delta=-20)
    if compact in AUTONOMY_MORE_TEXTS:
        return ModeIntent(kind="slider", slider="autonomy_level", delta=20)
    if compact in AUTONOMY_LESS_TEXTS:
        return ModeIntent(kind="slider", slider="autonomy_level", delta=-20)

    return None


def is_mode_intent_candidate(text: str) -> bool:
    return _deterministic_mode_intent(text) is not None


async def detect_mode_intent(
    text: str,
    paths: RuntimePaths | None = None,
    *,
    conversation_id: str | None = None,
) -> ModeIntent | None:
    _ = paths, conversation_id
    return _deterministic_mode_intent(text)


def mode_status_message(mode: dict[str, Any]) -> str:
    profile = mode.get("profile") if isinstance(mode.get("profile"), dict) else {}
    current = str(mode.get("current") or DEFAULT_MODE_ID)
    style_axis = int(profile.get("style_axis") or 0)
    detail_level = int(profile.get("detail_level") or 0)
    autonomy_level = int(profile.get("autonomy_level") or 0)
    style = "务实直接" if style_axis <= 35 else "温柔陪伴" if style_axis >= 70 else "平衡清楚"
    detail = "简短" if detail_level <= 35 else "详细" if detail_level >= 70 else "适中"
    autonomy = "多确认" if autonomy_level <= 35 else "更主动" if autonomy_level >= 70 else "平衡推进"
    return (
        f"当前回答风格是：{MODE_LABELS.get(current, current)}。"
        f"表达：{style}；细节：{detail}；自主：{autonomy}。"
    )


def _profile_defaults(mode_id: str, modes: list[dict[str, Any]]) -> dict[str, int] | None:
    profile = next((item for item in modes if str(item.get("id") or "") == mode_id), None)
    if not profile:
        return None
    return {
        "style_axis": int(profile.get("style_axis") or 0),
        "detail_level": int(profile.get("detail_level") or 0),
        "autonomy_level": int(profile.get("autonomy_level") or 0),
    }


async def apply_mode_intent(
    text: str,
    paths: RuntimePaths | None = None,
    *,
    conversation_id: str | None = None,
    scope: str | None = None,
) -> dict[str, Any] | None:
    runtime_paths = paths or ensure_runtime_dirs()
    intent = await detect_mode_intent(text, runtime_paths, conversation_id=conversation_id)
    if intent is None:
        return None

    current = get_current_mode(runtime_paths, conversation_id=conversation_id)
    if intent.kind == "query":
        return {
            "ok": True,
            "handled": True,
            "intent": {"kind": "query"},
            "message": mode_status_message(current),
            "mode": current,
            "changed": False,
        }

    profile = current["profile"]
    sliders = {
        "style_axis": int(profile.get("style_axis") or 0),
        "detail_level": int(profile.get("detail_level") or 0),
        "autonomy_level": int(profile.get("autonomy_level") or 0),
    }
    selected_mode = str(current.get("current") or DEFAULT_MODE_ID)

    if intent.kind == "mode" and intent.mode:
        selected_mode = intent.mode
        target_defaults = _profile_defaults(selected_mode, load_mode_profiles())
        if target_defaults is not None:
            sliders = target_defaults
    elif intent.kind == "slider" and intent.slider:
        minimum = 10 if intent.slider in SLIDER_KEYS else 0
        sliders[intent.slider] = max(minimum, min(100, sliders[intent.slider] + intent.delta))
        selected_mode = CUSTOM_MODE_ID

    updated = select_mode(
        selected_mode,
        runtime_paths,
        style_axis=sliders["style_axis"],
        detail_level=sliders["detail_level"],
        autonomy_level=sliders["autonomy_level"],
        conversation_id=conversation_id,
        scope=scope,
    )
    label = MODE_LABELS.get(str(updated.get("current") or selected_mode), selected_mode)
    message = mode_status_message(updated) if intent.kind == "slider" else f"已把回答风格调成：{label}。"
    return {
        "ok": True,
        "handled": True,
        "intent": {"kind": intent.kind, "mode": intent.mode, "slider": intent.slider, "delta": intent.delta},
        "message": message,
        "mode": updated,
        "changed": True,
    }


def slash_command_hint() -> str:
    return "不用输入代码式命令，可以直接说“切到务实一点”或“回答详细一点”。"
