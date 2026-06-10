from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

from .providers import load_provider_registry


def official_capability_boundaries() -> list[dict[str, str]]:
    return [
        {
            "capability": "conversation_agent_loop",
            "official_source": "run_agent.AIAgent.run_conversation + hermes_state.SessionDB",
            "lilsunspot_boundary": "桌面/微信普通对话只调用官方 agent loop；SQLite 只保存 UI 镜像和事件。",
        },
        {
            "capability": "provider_config",
            "official_source": "providers/base.ProviderProfile + Hermes config/env shape",
            "lilsunspot_boundary": "只写入产品层选择结果到独立 Hermes home，不维护分叉模型状态。",
        },
        {
            "capability": "weixin_text_and_media_send",
            "official_source": "gateway.platforms.weixin.WeixinAdapter / BasePlatformAdapter send methods",
            "lilsunspot_boundary": "扫码、审批和用户可见错误在产品层；实际发送调用官方 adapter。",
        },
        {
            "capability": "attachments",
            "official_source": "BasePlatformAdapter media/file delivery and WeixinAdapter upload implementation",
            "lilsunspot_boundary": "本地 attachment registry 只保存安全目录文件 ID；审批通过后把安全路径交给官方 adapter 发送链路。",
        },
        {
            "capability": "mode_profiles",
            "official_source": "Hermes prompt/config shape",
            "lilsunspot_boundary": "产品层 mode 只编译成 prompt/state 包装，不修改 Hermes core。",
        },
        {
            "capability": "safety_approval",
            "official_source": "tools.approval gateway approval queue",
            "lilsunspot_boundary": "审批队列 UI 保存在 lilsunspot data dir；决定结果映射回 Hermes approval queue。",
        },
        {
            "capability": "doctor_runtime",
            "official_source": "本地 sidecar + Hermes importable interfaces",
            "lilsunspot_boundary": "诊断只检查接口存在、版本记录和本地可调用性，不替代真实微信人工验收。",
        },
    ]


def _check(ok: bool, name: str, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _has_method(cls: type[Any], method_name: str, required_params: tuple[str, ...] = ()) -> tuple[bool, str]:
    method = getattr(cls, method_name, None)
    if not callable(method):
        return False, f"{cls.__name__}.{method_name} missing"
    if required_params:
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            return False, f"{cls.__name__}.{method_name} signature unavailable"
        missing = [param for param in required_params if param not in signature.parameters]
        if missing:
            return False, f"{cls.__name__}.{method_name} missing params: {', '.join(missing)}"
        return True, f"{cls.__name__}.{method_name}{signature}"
    return True, f"{cls.__name__}.{method_name} available"


def _upstream_commit() -> str:
    path = Path(__file__).resolve().parents[1] / "UPSTREAM_COMMIT.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def audit_hermes_compatibility() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    upstream_commit = _upstream_commit()
    checks.append(
        _check(
            bool(re.fullmatch(r"[0-9a-f]{40}", upstream_commit)),
            "hermes_upstream_commit_recorded",
            upstream_commit or "missing",
        )
    )

    try:
        from hermes_cli import __version__ as hermes_version
    except Exception as exc:  # noqa: BLE001 - diagnostic surface
        hermes_version = ""
        checks.append(_check(False, "hermes_version_importable", f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(_check(bool(hermes_version), "hermes_version_importable", str(hermes_version)))

    try:
        from hermes_state import SessionDB
        from run_agent import AIAgent
        from tools.approval import register_gateway_notify, resolve_gateway_approval
    except Exception as exc:  # noqa: BLE001 - diagnostic surface
        checks.append(_check(False, "hermes_agent_loop_importable", f"{type(exc).__name__}: {exc}"))
    else:
        ok, detail = _has_method(AIAgent, "run_conversation", ("user_message",))
        checks.append(_check(ok, "AIAgent.run_conversation", detail))
        ok, detail = _has_method(SessionDB, "get_messages_as_conversation", ("session_id",))
        checks.append(_check(ok, "SessionDB.get_messages_as_conversation", detail))
        ok, detail = _has_method(SessionDB, "delete_session", ("session_id",))
        checks.append(_check(ok, "SessionDB.delete_session", detail))
        checks.append(_check(callable(register_gateway_notify), "tools.approval.register_gateway_notify", "available"))
        checks.append(_check(callable(resolve_gateway_approval), "tools.approval.resolve_gateway_approval", "available"))

    try:
        from gateway.platforms.base import BasePlatformAdapter
        from gateway.platforms.weixin import WeixinAdapter, check_weixin_requirements
    except Exception as exc:  # noqa: BLE001 - diagnostic surface
        checks.append(_check(False, "hermes_gateway_importable", f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(_check(True, "hermes_gateway_importable", "gateway.platforms imported"))
        checks.append(
            _check(
                issubclass(WeixinAdapter, BasePlatformAdapter),
                "weixin_adapter_subclasses_base",
                "WeixinAdapter -> BasePlatformAdapter",
            )
        )
        for cls, methods in (
            (
                BasePlatformAdapter,
                {
                    "send": ("chat_id", "content"),
                    "send_document": ("chat_id", "file_path"),
                    "send_image_file": ("chat_id", "image_path"),
                    "send_video": ("chat_id", "video_path"),
                    "set_message_handler": ("handler",),
                    "set_fatal_error_handler": ("handler",),
                },
            ),
            (
                WeixinAdapter,
                {
                    "send": ("chat_id", "content"),
                    "send_document": ("chat_id", "file_path"),
                    "send_image_file": ("chat_id", "image_path"),
                    "send_video": ("chat_id", "video_path"),
                },
            ),
        ):
            for method_name, params in methods.items():
                ok, detail = _has_method(cls, method_name, params)
                checks.append(_check(ok, f"{cls.__name__}.{method_name}", detail))
        try:
            checks.append(
                _check(
                    bool(check_weixin_requirements()),
                    "weixin_runtime_dependencies_available",
                    "aiohttp + cryptography" if check_weixin_requirements() else "missing aiohttp or cryptography",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(_check(False, "weixin_runtime_dependencies_available", f"{type(exc).__name__}: {exc}"))

    try:
        registry = load_provider_registry()
    except Exception as exc:  # noqa: BLE001
        checks.append(_check(False, "provider_registry_hermes_mapping", f"{type(exc).__name__}: {exc}"))
    else:
        missing = [
            str(item.get("id") or "?")
            for item in registry
            if not str(item.get("hermes_provider") or "").strip()
        ]
        checks.append(
            _check(
                not missing and bool(registry),
                "provider_registry_hermes_mapping",
                f"{len(registry)} providers mapped" if not missing else "missing: " + ", ".join(missing),
            )
        )

    return {
        "ok": all(item["ok"] for item in checks),
        "hermes_version": hermes_version,
        "upstream_commit": upstream_commit,
        "capabilities": official_capability_boundaries(),
        "checks": checks,
    }
