from __future__ import annotations

import asyncio
from typing import Any

from hermes_constants import reset_hermes_home_override, set_hermes_home_override

from .attachments import AttachmentError, is_safe_stored_attachment
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .gateway import handle_weixin_message_event, load_weixin_credentials


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
    account_id = str(getattr(_adapter, "_account_id", "") or "").strip()
    if account_id:
        try:
            setattr(event, "account_id", account_id)
            source = getattr(event, "source", None)
            if source is not None:
                setattr(source, "account_id", account_id)
        except Exception:
            pass
    text = str(getattr(event, "text", "") or "").strip()
    media_urls = [str(item) for item in (getattr(event, "media_urls", None) or []) if str(item).strip()]
    media_types = [str(item) for item in (getattr(event, "media_types", None) or []) if str(item).strip()]
    if not text and not media_urls:
        return None

    result = await handle_weixin_message_event(event)
    if result.get("ok") and isinstance(result.get("chat"), dict):
        reply = str(result["chat"].get("reply") or "").strip()
    else:
        reply = str(result.get("message") or "").strip()
    if reply:
        _last_reply_at = _iso_now()
        return reply
    return None


async def send_approved_weixin_action(approval: dict[str, Any]) -> dict[str, Any]:
    if str(approval.get("operation") or "") != "send_weixin_message":
        return {"ok": True, "skipped": True, "message": "这个审批不需要微信发送。"}
    if str(approval.get("status") or "") != "approved":
        return {"ok": True, "skipped": True, "message": "审批未通过，不发送微信。"}
    adapter = _adapter
    if adapter is None or not getattr(adapter, "is_connected", False):
        return {"ok": False, "message": "微信还没有连接，暂时不能发送。"}

    details = approval.get("details") if isinstance(approval.get("details"), dict) else {}
    recipient = str(details.get("recipient") or "").strip()
    message = str(details.get("message") or details.get("message_preview") or "").strip()
    attachment_ids = [str(item) for item in details.get("attachment_ids", []) if str(item).strip()]
    if not recipient:
        return {"ok": False, "message": "微信联系人不能为空。"}

    files_to_send: list[tuple[str, str]] = []
    for attachment_id in attachment_ids:
        from . import conversations

        attachment = conversations.get_attachment(attachment_id, include_safe_path=True)
        if not attachment:
            return {"ok": False, "message": "没有找到要发送的附件。"}
        try:
            path = is_safe_stored_attachment(str(attachment.get("safe_path") or ""))
        except AttachmentError as exc:
            return {"ok": False, "message": str(exc)}
        suffix = path.suffix.lower()
        kind = "image" if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"} else "document"
        files_to_send.append((kind, str(path)))

    if message:
        result = await adapter.send(recipient, message)
        if not getattr(result, "success", False):
            return {"ok": False, "message": "微信文本发送失败。"}

    sent_files = 0
    for kind, path in files_to_send:
        if kind == "image":
            result = await adapter.send_image_file(recipient, path)
        else:
            result = await adapter.send_document(recipient, path)
        if not getattr(result, "success", False):
            return {"ok": False, "message": "微信文件发送失败。"}
        sent_files += 1

    return {
        "ok": True,
        "message": "微信发送已完成。",
        "sent_text": bool(message),
        "sent_files": sent_files,
    }


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
