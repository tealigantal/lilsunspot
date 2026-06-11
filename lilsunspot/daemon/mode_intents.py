from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .modes import CUSTOM_MODE_ID, DEFAULT_MODE_ID, get_current_mode, select_mode
from .providers import provider_by_id


MODE_ROUTER_TIMEOUT_SECONDS = 8.0
MODE_ROUTER_MAX_INPUT_CHARS = 80
MODE_ROUTER_CONFIDENCE_THRESHOLD = 0.7
SLIDER_KEYS = {"detail_level", "autonomy_level"}

MODE_LABELS = {
    "pragmatic": "务实",
    "balanced": "均衡",
    "emotional": "感性",
    "custom": "自定义",
}

MODE_STYLE_KEYWORDS = {
    "务实",
    "理性",
    "冷静",
    "均衡",
    "平衡",
    "感性",
    "温柔",
}

MODE_CONTROL_KEYWORDS = {
    "模式",
    "风格",
    "切到",
    "切换",
    "调成",
    "调整",
    "调到",
    "调为",
    "改成",
    "换成",
    "当前",
    "现在",
    "以后",
    "接下来",
    "回答再",
    "回复再",
    "回答详细",
    "回复详细",
    "更详细",
    "再详细",
    "回答简短",
    "回复简短",
    "更简短",
    "再简短",
    "短一点",
    "主动",
    "谨慎",
}


@dataclass(frozen=True)
class ModeIntent:
    kind: str
    mode: str | None = None
    slider: str | None = None
    delta: int = 0


def _is_short_router_candidate(text: str) -> bool:
    value = text.strip()
    if not value or value.startswith("/"):
        return False
    if "\n" in value or "\r" in value:
        return False
    return len(value) <= MODE_ROUTER_MAX_INPUT_CHARS


def is_mode_intent_candidate(text: str) -> bool:
    value = text.strip()
    if not _is_short_router_candidate(value):
        return False
    if any(keyword in value for keyword in MODE_CONTROL_KEYWORDS):
        return True
    if "一点" in value and any(keyword in value for keyword in MODE_STYLE_KEYWORDS):
        return True
    return False


def _router_prompt(modes: list[dict[str, Any]], current: dict[str, Any]) -> str:
    mode_options = [
        {
            "id": str(mode.get("id") or ""),
            "description": str(mode.get("description") or ""),
            "style_axis": int(mode.get("style_axis") or 0),
            "detail_level": int(mode.get("detail_level") or 0),
            "autonomy_level": int(mode.get("autonomy_level") or 0),
        }
        for mode in modes
        if str(mode.get("id") or "").strip()
    ]
    current_profile = current.get("profile") if isinstance(current.get("profile"), dict) else {}
    current_state = {
        "current": str(current.get("current") or ""),
        "style_axis": int(current_profile.get("style_axis") or 0),
        "detail_level": int(current_profile.get("detail_level") or 0),
        "autonomy_level": int(current_profile.get("autonomy_level") or 0),
    }
    return (
        "你是小黑子的内部意图路由器，只判断用户这句话是否在控制回答风格。"
        "不要回答用户，不要执行任务，只输出一个 JSON 对象。\n"
        "可选模式和滑杆来自系统配置，不要发明新模式：\n"
        f"{json.dumps({'modes': mode_options, 'current': current_state}, ensure_ascii=False)}\n"
        "输出格式："
        '{"kind":"chat|query|mode|slider","mode":null,"slider":null,"delta":0,"confidence":0.0}\n'
        "规则：如果用户是在问当前风格，kind=query。"
        "如果用户要求切换整体回答风格，kind=mode，mode 必须是可选模式 id。"
        "如果用户只要求回答更详细/更简短或推进更主动/更谨慎，kind=slider，"
        "slider 只能是 detail_level 或 autonomy_level，delta 只能是 20 或 -20。"
        "如果用户是在让你写作、解释、分析、总结、处理文件或正常聊天，kind=chat。"
        "不能确定时 kind=chat，confidence 低于 0.7。"
    )


def _router_payload(model: str, system_prompt: str, text: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text.strip()},
        ],
        "temperature": 0,
        "max_tokens": 160,
        "stream": False,
    }


def _extract_json_object(text: str) -> dict[str, Any] | None:
    value = text.strip()
    if not value:
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(value[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _coerce_router_intent(payload: dict[str, Any], modes: list[dict[str, Any]]) -> ModeIntent | None:
    try:
        confidence = float(payload.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    if confidence < MODE_ROUTER_CONFIDENCE_THRESHOLD:
        return None

    kind = str(payload.get("kind") or "").strip().lower()
    if kind == "chat":
        return None
    if kind == "query":
        return ModeIntent(kind="query")

    if kind == "mode":
        mode = str(payload.get("mode") or "").strip()
        available_modes = {str(item.get("id") or "") for item in modes}
        if mode in available_modes:
            return ModeIntent(kind="mode", mode=mode)
        return None

    if kind == "slider":
        slider = str(payload.get("slider") or "").strip()
        if slider not in SLIDER_KEYS:
            return None
        try:
            raw_delta = int(payload.get("delta") or 0)
        except (TypeError, ValueError):
            return None
        delta = 20 if raw_delta > 0 else -20 if raw_delta < 0 else 0
        if delta:
            return ModeIntent(kind="slider", slider=slider, delta=delta)
        return None

    return None


async def _call_mode_router_model(text: str, paths: RuntimePaths) -> str | None:
    from . import chat_client
    from . import provider_client as provider_http

    error, settings = chat_client._load_chat_settings(paths)
    if error is not None or settings is None:
        return None

    provider_config = provider_by_id(str(settings["provider"]))
    if provider_config is None:
        return None
    provider_config = dict(provider_config)
    configured_provider = settings.get("provider_config")
    if isinstance(configured_provider, dict) and configured_provider.get("base_url"):
        provider_config["base_url"] = configured_provider["base_url"]

    try:
        base_url = provider_http._provider_base_url(provider_config)
    except provider_http.ProviderValidationError:
        return None

    current = get_current_mode(paths)
    modes = load_mode_profiles_for_router()
    timeout = httpx.Timeout(MODE_ROUTER_TIMEOUT_SECONDS, connect=5.0)
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=False) as client:
            response = await client.post(
                "chat/completions",
                headers=chat_client._chat_request_headers(str(settings["api_key"])),
                json=_router_payload(str(settings["model"]), _router_prompt(modes, current), text),
            )
    except (httpx.InvalidURL, httpx.RequestError):
        return None

    payload = provider_http._safe_json(response)
    if response.status_code >= 400:
        return None
    reply = chat_client._extract_reply(payload)
    return reply or None


def load_mode_profiles_for_router() -> list[dict[str, Any]]:
    from .modes import load_mode_profiles

    return load_mode_profiles()


def _profile_defaults(mode_id: str, modes: list[dict[str, Any]]) -> dict[str, int] | None:
    profile = next((item for item in modes if str(item.get("id") or "") == mode_id), None)
    if not profile:
        return None
    return {
        "style_axis": int(profile.get("style_axis") or 0),
        "detail_level": int(profile.get("detail_level") or 0),
        "autonomy_level": int(profile.get("autonomy_level") or 0),
    }


async def _route_mode_intent_with_model(text: str, paths: RuntimePaths) -> ModeIntent | None:
    if not _is_short_router_candidate(text):
        return None
    modes = load_mode_profiles_for_router()
    reply = await _call_mode_router_model(text, paths)
    if reply is None:
        return None
    payload = _extract_json_object(reply)
    if payload is None:
        return None
    return _coerce_router_intent(payload, modes)


async def detect_mode_intent(text: str, paths: RuntimePaths | None = None) -> ModeIntent | None:
    if not is_mode_intent_candidate(text):
        return None
    return await _route_mode_intent_with_model(text, paths or ensure_runtime_dirs())


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


async def apply_mode_intent(text: str, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    runtime_paths = paths or ensure_runtime_dirs()
    intent = await detect_mode_intent(text, runtime_paths)
    if intent is None:
        return None

    current = get_current_mode(runtime_paths)
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
        target_defaults = _profile_defaults(selected_mode, load_mode_profiles_for_router())
        if target_defaults is not None:
            sliders = target_defaults
    elif intent.kind == "slider" and intent.slider:
        minimum = 10 if intent.slider in {"detail_level", "autonomy_level"} else 0
        sliders[intent.slider] = max(minimum, min(100, sliders[intent.slider] + intent.delta))
        selected_mode = CUSTOM_MODE_ID

    updated = select_mode(
        selected_mode,
        runtime_paths,
        style_axis=sliders["style_axis"],
        detail_level=sliders["detail_level"],
        autonomy_level=sliders["autonomy_level"],
    )
    label = MODE_LABELS.get(str(updated.get("current") or selected_mode), selected_mode)
    if intent.kind == "slider":
        message = mode_status_message(updated)
    else:
        message = f"已把回答风格调成：{label}。"
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
