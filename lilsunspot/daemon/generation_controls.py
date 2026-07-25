from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import conversations
from .config_paths import RuntimePaths
from .providers import load_yaml_resource


GENERATION_PROFILES_FILE = Path(__file__).resolve().parents[1] / "resources" / "default_generation_profiles.yaml"
GENERATION_STATE_FILE = "generation-control.json"
GENERATION_COMPATIBILITY_FILE = "generation-compatibility.json"
CONVERSATION_METADATA_KEY = "generation_control"
PARAMETER_KEYS = ("temperature", "top_p", "top_k", "max_tokens", "reasoning_effort", "max_iterations", "seed")
REQUEST_OVERRIDE_KEYS = ("temperature", "top_p", "top_k", "seed")
REASONING_VALUES = ("none", "low", "medium", "high", "max")
SOURCE_LABELS = {
    "mode_preset": "模式预设",
    "global_override": "全局覆盖",
    "conversation_override": "会话覆盖",
    "turn_override": "单轮覆盖",
    "model_locked": "模型锁定",
}
_OPENROUTER_CACHE: dict[str, dict[str, Any] | None] = {}


class GenerationControlError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_generation_profiles() -> dict[str, dict[str, Any]]:
    raw = load_yaml_resource(GENERATION_PROFILES_FILE)
    profiles = raw.get("profiles") if isinstance(raw, dict) else None
    if not isinstance(profiles, dict):
        raise GenerationControlError("生成模式资源无效。")
    return {str(key): dict(value) for key, value in profiles.items() if isinstance(value, dict)}


def generation_modes_catalog() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for mode_id, profile in load_generation_profiles().items():
        if mode_id == "custom":
            continue
        result.append(
            {
                "id": mode_id,
                "label": str(profile.get("label") or mode_id),
                "description": str(profile.get("description") or ""),
                "effects": dict(profile.get("effects") or {}),
            }
        )
    return result


def _state_path(paths: RuntimePaths) -> Path:
    return paths.data_dir / GENERATION_STATE_FILE


def _compatibility_path(paths: RuntimePaths) -> Path:
    return paths.data_dir / GENERATION_COMPATIBILITY_FILE


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return value if isinstance(value, dict) else dict(fallback)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _number(value: Any, *, minimum: float, maximum: float, integer: bool = False) -> int | float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GenerationControlError("生成参数必须是有效数字。") from exc
    if not minimum <= number <= maximum:
        raise GenerationControlError(f"生成参数必须在 {minimum:g} 到 {maximum:g} 之间。")
    return int(number) if integer else number


def normalize_parameters(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GenerationControlError("生成参数必须是对象。")
    unknown = sorted(set(raw) - set(PARAMETER_KEYS))
    if unknown:
        raise GenerationControlError(f"不认识的生成参数：{', '.join(unknown)}。")
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None or value == "":
            normalized[key] = None
        elif key == "temperature":
            normalized[key] = _number(value, minimum=0, maximum=2)
        elif key in {"top_p"}:
            normalized[key] = _number(value, minimum=0, maximum=1)
        elif key == "top_k":
            normalized[key] = _number(value, minimum=1, maximum=1000, integer=True)
        elif key == "max_tokens":
            normalized[key] = _number(value, minimum=1, maximum=1_000_000, integer=True)
        elif key == "max_iterations":
            normalized[key] = _number(value, minimum=1, maximum=90, integer=True)
        elif key == "seed":
            normalized[key] = _number(value, minimum=0, maximum=2_147_483_647, integer=True)
        elif key == "reasoning_effort":
            effort = str(value).strip().lower()
            if effort not in REASONING_VALUES:
                raise GenerationControlError("推理强度只支持 none、low、medium、high 或 max。")
            normalized[key] = effort
    return normalized


def normalize_selection(raw: Any, *, require_value: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GenerationControlError("生成控制设置必须是对象。")
    result: dict[str, Any] = {}
    if "mode" in raw:
        mode = str(raw.get("mode") or "").strip().lower()
        if mode not in load_generation_profiles():
            raise GenerationControlError("不认识的生成模式。")
        result["mode"] = mode
    if "parameters" in raw:
        result["parameters"] = normalize_parameters(raw.get("parameters"))
    if require_value and not result:
        raise GenerationControlError("请选择生成模式或设置参数。")
    return result


def _global_selection(paths: RuntimePaths) -> dict[str, Any]:
    value = _read_json(_state_path(paths), {"mode": "balanced", "parameters": {}})
    try:
        normalized = normalize_selection(value)
    except GenerationControlError:
        return {"mode": "balanced", "parameters": {}}
    normalized.setdefault("mode", "balanced")
    normalized.setdefault("parameters", {})
    return normalized


def _conversation_selection(paths: RuntimePaths, conversation_id: str | None) -> dict[str, Any]:
    if not conversation_id:
        return {}
    conversation = conversations.get_conversation(conversation_id, paths)
    metadata = conversation.get("metadata") if isinstance(conversation, dict) else {}
    raw = metadata.get(CONVERSATION_METADATA_KEY) if isinstance(metadata, dict) else None
    if not isinstance(raw, dict):
        return {}
    try:
        return normalize_selection(raw)
    except GenerationControlError:
        return {}


def save_generation_selection(
    paths: RuntimePaths,
    *,
    scope: str,
    selection: dict[str, Any],
    conversation_id: str | None = None,
) -> dict[str, Any]:
    scope = str(scope or "").strip().lower()
    normalized = normalize_selection(selection, require_value=True)
    if scope == "global":
        current = _global_selection(paths)
        current.update(normalized)
        _write_json(_state_path(paths), current)
        return current
    if scope == "conversation":
        if not conversation_id:
            raise GenerationControlError("会话覆盖需要 conversation_id。")
        conversation = conversations.get_conversation(conversation_id, paths)
        if conversation is None:
            raise GenerationControlError("找不到这个对话。")
        current = _conversation_selection(paths, conversation_id)
        current.update(normalized)
        conversations.update_conversation(
            conversation_id,
            metadata_patch={CONVERSATION_METADATA_KEY: current},
            paths=paths,
        )
        return current
    if scope == "turn":
        return normalized
    raise GenerationControlError("生成控制范围只支持 global、conversation 或 turn。")


def reset_generation_selection(paths: RuntimePaths, *, scope: str, conversation_id: str | None = None) -> None:
    scope = str(scope or "").strip().lower()
    if scope == "global":
        _write_json(_state_path(paths), {"mode": "balanced", "parameters": {}})
        return
    if scope == "conversation":
        if not conversation_id:
            raise GenerationControlError("会话覆盖需要 conversation_id。")
        if conversations.get_conversation(conversation_id, paths) is None:
            raise GenerationControlError("找不到这个对话。")
        conversations.update_conversation(
            conversation_id,
            metadata_patch={CONVERSATION_METADATA_KEY: {}},
            paths=paths,
        )
        return
    raise GenerationControlError("恢复默认值只支持 global 或 conversation。")


def _resolved_selection(
    paths: RuntimePaths,
    conversation_id: str | None,
    turn_override: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any], dict[str, str]]:
    profiles = load_generation_profiles()
    global_selection = _global_selection(paths)
    conversation_selection = _conversation_selection(paths, conversation_id)
    turn_selection = normalize_selection(turn_override) if isinstance(turn_override, dict) else {}
    mode = str(global_selection.get("mode") or "balanced")
    mode_scope = "global"
    if conversation_selection.get("mode"):
        mode = str(conversation_selection["mode"])
        mode_scope = "conversation"
    if turn_selection.get("mode"):
        mode = str(turn_selection["mode"])
        mode_scope = "turn"
    profile = profiles.get(mode) or profiles["balanced"]
    requested = dict(profile.get("parameters") or {})
    sources = {key: "mode_preset" for key in requested}
    for selection, source in (
        (global_selection, "global_override"),
        (conversation_selection, "conversation_override"),
        (turn_selection, "turn_override"),
    ):
        for key, value in dict(selection.get("parameters") or {}).items():
            requested[key] = value
            sources[key] = source
    return mode, mode_scope, requested, sources


def _recorded_rejections(paths: RuntimePaths, provider: str, model: str) -> dict[str, Any]:
    all_rejections = _read_json(_compatibility_path(paths), {})
    value = all_rejections.get(f"{provider.lower()}::{model.lower()}")
    return dict(value) if isinstance(value, dict) else {}


def record_parameter_rejection(paths: RuntimePaths, provider: str, model: str, parameter: str) -> None:
    if parameter not in PARAMETER_KEYS:
        return
    path = _compatibility_path(paths)
    all_rejections = _read_json(path, {})
    key = f"{provider.lower()}::{model.lower()}"
    current = all_rejections.get(key) if isinstance(all_rejections.get(key), dict) else {}
    current[parameter] = {"reason": "Provider 明确拒绝了此参数。", "updated_at": _now_iso()}
    all_rejections[key] = current
    _write_json(path, all_rejections)


def rejected_parameter_from_error(error: str, candidates: list[str]) -> str | None:
    lowered = str(error or "").lower()
    rejection_words = ("unsupported", "not support", "unrecognized", "unknown parameter", "invalid parameter", "extra_forbidden")
    if not any(word in lowered for word in rejection_words):
        return None
    for parameter in candidates:
        patterns = {parameter.lower(), parameter.lower().replace("_", " ")}
        if parameter == "max_tokens":
            patterns.add("max_completion_tokens")
        if any(re.search(rf"\b{re.escape(pattern)}\b", lowered) for pattern in patterns):
            return parameter
    return None


def _openrouter_model_metadata(model: str) -> dict[str, Any] | None:
    if model in _OPENROUTER_CACHE:
        return _OPENROUTER_CACHE[model]
    try:
        response = requests.get(f"https://openrouter.ai/api/v1/models/{model}", timeout=3)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        value = data if isinstance(data, dict) else None
    except Exception:
        value = None
    _OPENROUTER_CACHE[model] = value
    return value


def _model_metadata(provider: str, hermes_provider: str, model: str) -> tuple[Any, dict[str, Any] | None]:
    try:
        from agent.models_dev import get_model_info

        info = get_model_info(provider, model) or get_model_info(hermes_provider, model)
    except Exception:
        info = None
    openrouter = _openrouter_model_metadata(model) if provider.lower() == "openrouter" else None
    return info, openrouter


def _parameter_capability(
    *,
    parameter: str,
    provider: str,
    hermes_provider: str,
    model: str,
    model_info: Any,
    openrouter: dict[str, Any] | None,
    rejections: dict[str, Any],
) -> dict[str, Any]:
    provider_id = provider.lower()
    hermes_id = hermes_provider.lower()
    supported_parameters = set(openrouter.get("supported_parameters") or []) if isinstance(openrouter, dict) else set()
    defaults = openrouter.get("default_parameters") if isinstance(openrouter, dict) and isinstance(openrouter.get("default_parameters"), dict) else {}
    if parameter in rejections:
        return {"status": "unsupported", "reason": "Provider 曾明确拒绝此参数。", "default": defaults.get(parameter)}
    if parameter == "max_iterations":
        return {"status": "supported", "range": {"min": 1, "max": 90}, "default": 90}
    try:
        from providers import get_provider_profile
        from providers.base import OMIT_TEMPERATURE

        profile = get_provider_profile(hermes_provider)
    except Exception:
        profile = None
        OMIT_TEMPERATURE = object()
    if parameter == "temperature" and profile is not None and profile.fixed_temperature is OMIT_TEMPERATURE:
        return {"status": "locked", "reason": "此模型由服务端控制随机性。", "default": None}
    if parameter == "temperature" and profile is not None and profile.fixed_temperature is not None:
        return {"status": "locked", "reason": "此 Provider 锁定了随机性参数。", "default": profile.fixed_temperature, "locked_value": profile.fixed_temperature}
    local_ollama = provider_id == "ollama" or hermes_id == "ollama"
    if parameter == "max_tokens":
        maximum = int(getattr(model_info, "max_output", 0) or 0) or 1_000_000
        default = getattr(profile, "default_max_tokens", None) if profile is not None else None
        return {"status": "supported", "range": {"min": 1, "max": maximum}, "default": default}
    if parameter == "reasoning_effort":
        reasoning = bool(getattr(model_info, "reasoning", False))
        openrouter_reasoning = bool(supported_parameters & {"reasoning", "reasoning_effort"})
        if reasoning or local_ollama or provider_id in {"deepseek", "kimi", "moonshot"} or openrouter_reasoning:
            allowed = ["none", "low", "medium", "high", "max"]
            if provider_id == "deepseek":
                allowed = ["high", "max"]
            return {"status": "supported", "values": allowed, "default": defaults.get(parameter)}
        return {"status": "unsupported", "reason": "当前模型未声明推理强度控制。", "default": None}
    if parameter == "temperature":
        if supported_parameters:
            supported = parameter in supported_parameters
        elif model_info is not None:
            supported = bool(getattr(model_info, "temperature", False)) or local_ollama
        else:
            supported = local_ollama or provider_id in {"deepseek", "qwen", "openai"}
        return ({"status": "supported", "range": {"min": 0, "max": 2}, "default": defaults.get(parameter)} if supported else {"status": "unsupported", "reason": "此模型由服务端控制随机性。", "default": None})
    if parameter == "top_p":
        if supported_parameters:
            supported = parameter in supported_parameters
        elif provider_id == "openrouter":
            supported = False
        elif provider_id == "openai" and bool(getattr(model_info, "reasoning", False)):
            supported = False
        else:
            supported = local_ollama or provider_id in {"deepseek", "qwen", "openai"}
        return ({"status": "supported", "range": {"min": 0, "max": 1}, "default": defaults.get(parameter)} if supported else {"status": "unsupported", "reason": "当前模型未声明支持 top-p。", "default": None})
    if parameter == "top_k":
        supported = bool(supported_parameters and parameter in supported_parameters)
        return ({"status": "supported", "range": {"min": 1, "max": 1000}, "default": defaults.get(parameter)} if supported else {"status": "unsupported", "reason": "当前模型未声明支持 top-k。", "default": None})
    if parameter == "seed":
        supported = local_ollama or bool(supported_parameters and parameter in supported_parameters)
        return ({"status": "supported", "range": {"min": 0, "max": 2_147_483_647}, "default": defaults.get(parameter)} if supported else {"status": "unsupported", "reason": "当前模型未声明支持 seed。", "default": None})
    return {"status": "unsupported", "reason": "当前模型未声明支持此参数。", "default": None}


def _fallback_supports(parameter: str, fallback_chain: list[dict[str, Any]]) -> bool:
    for fallback in fallback_chain:
        provider = str(fallback.get("provider") or "").lower()
        if parameter in {"max_iterations", "max_tokens"}:
            continue
        if parameter == "temperature" and provider not in {"ollama", "deepseek", "alibaba", "qwen", "openai", "openrouter"}:
            return False
        if parameter == "top_p" and provider not in {"ollama", "deepseek", "alibaba", "qwen", "openai", "openrouter"}:
            return False
        if parameter == "top_k" and provider != "openrouter":
            return False
        if parameter == "seed" and provider not in {"ollama", "openai", "openrouter"}:
            return False
        if parameter == "reasoning_effort" and provider not in {"ollama", "deepseek", "openai", "openrouter"}:
            return False
    return True


def resolve_generation_control(
    paths: RuntimePaths,
    *,
    provider: str,
    hermes_provider: str,
    model: str,
    conversation_id: str | None = None,
    turn_override: dict[str, Any] | None = None,
    fallback_chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    provider = str(provider or "custom").strip() or "custom"
    hermes_provider = str(hermes_provider or provider).strip() or provider
    model = str(model or "").strip()
    mode, mode_scope, requested, sources = _resolved_selection(paths, conversation_id, turn_override)
    profiles = load_generation_profiles()
    profile = profiles.get(mode) or profiles["balanced"]
    model_info, openrouter = _model_metadata(provider, hermes_provider, model)
    rejections = _recorded_rejections(paths, provider, model)
    parameter_details: dict[str, dict[str, Any]] = {}
    effective: dict[str, Any] = {}
    fallback_chain = list(fallback_chain or [])
    for parameter in PARAMETER_KEYS:
        capability = _parameter_capability(
            parameter=parameter,
            provider=provider,
            hermes_provider=hermes_provider,
            model=model,
            model_info=model_info,
            openrouter=openrouter,
            rejections=rejections,
        )
        requested_value = requested.get(parameter)
        source = sources.get(parameter, "mode_preset")
        detail = {
            "requested": requested_value,
            "effective": None,
            "source": source,
            "source_label": SOURCE_LABELS.get(source, source),
            **capability,
        }
        if requested_value is None:
            detail["status"] = "default" if capability.get("status") == "supported" else capability.get("status")
            if detail["status"] == "default":
                detail["reason"] = "已恢复模型默认值，请求中省略此字段。"
        elif capability.get("status") == "supported":
            value = requested_value
            allowed = capability.get("values")
            if isinstance(allowed, list) and value not in allowed:
                value = None
                detail["status"] = "omitted"
                detail["reason"] = f"当前模型只接受：{', '.join(allowed)}，已省略此参数并交给模型决定。"
                detail["degraded"] = True
            value_range = capability.get("range")
            if value is not None and isinstance(value_range, dict) and isinstance(value, (int, float)):
                minimum = value_range.get("min")
                maximum = value_range.get("max")
                clamped = value
                if isinstance(minimum, (int, float)):
                    clamped = max(minimum, clamped)
                if isinstance(maximum, (int, float)):
                    clamped = min(maximum, clamped)
                if clamped != value:
                    value = int(clamped) if isinstance(requested_value, int) else clamped
                    detail["reason"] = "请求值超出当前模型范围，已收紧到支持范围内。"
                    detail["degraded"] = True
            if value is not None and _fallback_supports(parameter, fallback_chain):
                detail["effective"] = value
                effective[parameter] = value
            elif value is not None:
                detail["status"] = "omitted"
                detail["reason"] = "备用模型链未确认支持，已保守省略此参数。"
                detail["degraded"] = True
        elif capability.get("status") == "locked":
            detail["source"] = "model_locked"
            detail["source_label"] = SOURCE_LABELS["model_locked"]
            detail["effective"] = capability.get("locked_value")
        parameter_details[parameter] = detail

    if "temperature" in effective and "top_p" in effective and provider.lower() == "deepseek":
        effective.pop("top_p", None)
        detail = parameter_details["top_p"]
        detail.update(
            {
                "effective": None,
                "status": "omitted",
                "reason": "此模型不同时发送 temperature 与 top-p，已保留 temperature。",
                "degraded": True,
            }
        )

    request_overrides = {key: effective[key] for key in REQUEST_OVERRIDE_KEYS if key in effective}
    max_tokens = effective.get("max_tokens")
    max_iterations = int(effective.get("max_iterations") or 90)
    reasoning_effort = effective.get("reasoning_effort")
    auto_degraded = any(bool(item.get("degraded")) for item in parameter_details.values())
    unsupported_requested = [
        key
        for key, item in parameter_details.items()
        if item.get("requested") is not None and item.get("effective") is None and item.get("status") in {"unsupported", "locked", "omitted"}
    ]
    return {
        "mode": mode,
        "mode_scope": mode_scope,
        "label": str(profile.get("label") or mode),
        "description": str(profile.get("description") or ""),
        "effects": dict(profile.get("effects") or {}),
        "provider": provider,
        "model": model,
        "fully_supported": not unsupported_requested and not auto_degraded,
        "compatibility_summary": "当前模型完整支持此模式。" if not unsupported_requested and not auto_degraded else "当前模型已省略或调整部分不支持的参数。",
        "requested_parameters": requested,
        "effective_parameters": effective,
        "parameters": parameter_details,
        "runtime": {
            "request_overrides": request_overrides,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
            "max_iterations": max_iterations,
        },
        "automatic_downgrade": auto_degraded,
        "retry_count": 0,
    }


def public_execution_trace(control: dict[str, Any], *, tool_iterations: int, retry_count: int = 0) -> dict[str, Any]:
    omitted = []
    for key, item in dict(control.get("parameters") or {}).items():
        if item.get("requested") is not None and item.get("effective") is None:
            omitted.append({"parameter": key, "status": item.get("status"), "reason": item.get("reason")})
    runtime = control.get("runtime") if isinstance(control.get("runtime"), dict) else {}
    return {
        "provider": str(control.get("provider") or ""),
        "model": str(control.get("model") or ""),
        "mode": str(control.get("mode") or ""),
        "mode_label": str(control.get("label") or ""),
        "effective_parameters": dict(control.get("effective_parameters") or {}),
        "omitted_parameters": omitted,
        "reasoning_effort": runtime.get("reasoning_effort"),
        "tool_iterations": max(0, int(tool_iterations)),
        "max_iterations": int(runtime.get("max_iterations") or 90),
        "automatic_downgrade": bool(control.get("automatic_downgrade")) or retry_count > 0,
        "retry_count": max(0, int(retry_count)),
    }
