from __future__ import annotations

import re
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from . import conversations
from .attachments import is_safe_stored_attachment
from .config_paths import RuntimePaths


_CURRENT_TURN: ContextVar["DeliveryTurnContext | None"] = ContextVar("lilsunspot_delivery_turn", default=None)
_ATTACHMENT_ID_RE = re.compile(r"^att_[A-Za-z0-9_-]+$")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


@dataclass
class DeliveryTurnContext:
    conversation_id: str
    source: str
    route: dict[str, str] | None
    paths: RuntimePaths
    actions: list[dict[str, Any]] = field(default_factory=list)
    _action_by_attachment: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def target(self) -> str:
        return "weixin_current_route" if self.route else "desktop_current_conversation"

    def add_action(self, action: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(action.get("attachment_id") or "")
        if action.get("ok") and attachment_id:
            existing = self._action_by_attachment.get(attachment_id)
            if existing is not None:
                return _public_action({**existing, "duplicate": True})
            self._action_by_attachment[attachment_id] = action
        self.actions.append(action)
        return _public_action(action)

    def actions_for_result(self) -> list[dict[str, Any]]:
        return [_public_action(action) for action in self.actions]


def current_delivery_turn() -> DeliveryTurnContext | None:
    return _CURRENT_TURN.get()


@contextmanager
def delivery_turn_context(
    *,
    conversation_id: str,
    source: str,
    route: dict[str, str] | None,
    paths: RuntimePaths,
) -> Iterator[DeliveryTurnContext]:
    context = DeliveryTurnContext(
        conversation_id=conversation_id,
        source=source,
        route=route,
        paths=paths,
    )
    token = _CURRENT_TURN.set(context)
    try:
        yield context
    finally:
        _CURRENT_TURN.reset(token)


def return_attachment_action(attachment_id: str, caption: str = "") -> dict[str, Any]:
    context = current_delivery_turn()
    if context is None:
        return _failed_action(attachment_id, "no_active_turn")

    attachment_id = str(attachment_id or "").strip()
    if not _ATTACHMENT_ID_RE.match(attachment_id):
        return context.add_action(_failed_action(attachment_id, "invalid_attachment_id", target=context.target))

    attachment = conversations.get_attachment(attachment_id, include_safe_path=True, paths=context.paths)
    if not attachment:
        return context.add_action(_failed_action(attachment_id, "missing_attachment", target=context.target))

    if str(attachment.get("conversation_id") or "") != context.conversation_id:
        return context.add_action(_failed_action(attachment_id, "cross_conversation", target=context.target))

    try:
        safe_path = is_safe_stored_attachment(str(attachment.get("safe_path") or ""), context.paths)
    except Exception:
        return context.add_action(_failed_action(attachment_id, "unsafe_path", target=context.target))

    action = {
        "ok": True,
        "action_id": f"da_{secrets.token_hex(8)}",
        "attachment_id": attachment_id,
        "safe_path": str(safe_path),
        "file_name": str(attachment.get("file_name") or Path(safe_path).name),
        "mime_type": str(attachment.get("mime_type") or "application/octet-stream"),
        "media_kind": _media_kind(attachment, safe_path),
        "caption": _clean_caption(caption),
        "target": context.target,
        "status": "pending",
    }
    return context.add_action(action)


def _failed_action(attachment_id: str, reason_code: str, *, target: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "action_id": f"da_{secrets.token_hex(8)}",
        "attachment_id": str(attachment_id or "").strip(),
        "file_name": "",
        "mime_type": "",
        "media_kind": "",
        "caption": "",
        "target": target,
        "status": "rejected",
        "reason_code": reason_code,
    }


def _media_kind(attachment: dict[str, Any], safe_path: Path) -> str:
    mime_type = str(attachment.get("mime_type") or "").lower()
    if mime_type.startswith("image/") or safe_path.suffix.lower() in _IMAGE_EXTS:
        return "image"
    return "document"


def _clean_caption(caption: str) -> str:
    value = " ".join(str(caption or "").split())
    if len(value) > 240:
        value = value[:240].rstrip()
    return value


def _public_action(action: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "ok",
        "action_id",
        "attachment_id",
        "file_name",
        "mime_type",
        "media_kind",
        "caption",
        "target",
        "status",
        "reason_code",
        "duplicate",
    }
    return {key: value for key, value in action.items() if key in allowed}
