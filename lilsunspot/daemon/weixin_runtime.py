from __future__ import annotations

import asyncio
from typing import Any

from hermes_constants import reset_hermes_home_override, set_hermes_home_override

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .gateway import handle_weixin_command_text, load_weixin_credentials


_adapter: Any | None = None
_state = "stopped"
_last_inbound_at = ""
_last_reply_at = ""
_last_error = ""
_lock: asyncio.Lock | None = None


def _runtime_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _iso_now() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def weixin_runtime_status() -> dict[str, Any]:
    running = bool(_adapter is not None and getattr(_adapter, "is_connected", False))
    state = "running" if running and _state != "error" else _state
    return {
        "state": state,
        "running": running,
        "last_inbound_at": _last_inbound_at,
        "last_reply_at": _last_reply_at,
        "last_error": _last_error,
    }


def _set_state(state: str, error: str = "") -> None:
    global _state, _last_error
    _state = state
    _last_error = error


async def _handle_adapter_fatal_error(adapter: Any) -> None:
    message = str(getattr(adapter, "_fatal_error_message", "") or "微信运行时发生错误。")
    _set_state("error", message)


async def handle_inbound_weixin_event(event: Any) -> str | None:
    global _last_inbound_at, _last_reply_at

    _last_inbound_at = _iso_now()
    text = str(getattr(event, "text", "") or "").strip()
    if not text:
        _last_reply_at = _iso_now()
        return "当前微信入口只支持文字私聊。"

    result = await handle_weixin_command_text(text)
    if result.get("ok") and isinstance(result.get("chat"), dict):
        reply = str(result["chat"].get("reply") or "").strip()
    else:
        reply = str(result.get("message") or "").strip()
    if reply:
        _last_reply_at = _iso_now()
        return reply
    return None


def _make_weixin_adapter(credentials: dict[str, str]) -> Any:
    from gateway.config import PlatformConfig
    from gateway.platforms.weixin import WeixinAdapter

    user_id = str(credentials.get("user_id") or "").strip()
    config = PlatformConfig(
        enabled=True,
        token=str(credentials["token"]),
        gateway_restart_notification=False,
        extra={
            "account_id": str(credentials["account_id"]),
            "base_url": str(credentials.get("base_url") or ""),
            "dm_policy": "allowlist",
            "allow_from": user_id,
            "group_policy": "disabled",
            "split_multiline_messages": False,
        },
    )
    return WeixinAdapter(config)


async def start_weixin_runtime(paths: RuntimePaths | None = None) -> dict[str, Any]:
    global _adapter

    runtime_paths = paths or ensure_runtime_dirs()
    async with _runtime_lock():
        if _adapter is not None and getattr(_adapter, "is_connected", False):
            return weixin_runtime_status()

        credentials = load_weixin_credentials(runtime_paths)
        if not credentials:
            _adapter = None
            _set_state("stopped", "")
            return weixin_runtime_status()
        if not str(credentials.get("user_id") or "").strip():
            _adapter = None
            _set_state("error", "微信扫码凭据缺少用户 ID，请重新扫码。")
            return weixin_runtime_status()

        _set_state("starting", "")
        home_token = set_hermes_home_override(runtime_paths.hermes_home)
        try:
            adapter = _make_weixin_adapter(credentials)
            adapter.set_message_handler(handle_inbound_weixin_event)
            adapter.set_fatal_error_handler(_handle_adapter_fatal_error)
            connected = await adapter.connect()
        except Exception:
            _adapter = None
            _set_state("error", "微信运行时启动失败，请重新扫码或稍后再试。")
            return weixin_runtime_status()
        finally:
            reset_hermes_home_override(home_token)

        if not connected:
            _adapter = None
            _set_state("error", "微信运行时没有连接成功，请重新扫码。")
            return weixin_runtime_status()

        _adapter = adapter
        _set_state("running", "")
        return weixin_runtime_status()


async def stop_weixin_runtime() -> dict[str, Any]:
    global _adapter

    async with _runtime_lock():
        adapter = _adapter
        _adapter = None
        if adapter is not None:
            try:
                await adapter.disconnect()
            except Exception:
                _set_state("error", "微信运行时断开失败。")
                return weixin_runtime_status()
        _set_state("stopped", "")
        return weixin_runtime_status()
