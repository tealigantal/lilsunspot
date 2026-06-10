from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs


DB_FILE_NAME = "lilsunspot-conversations.sqlite3"
PERSONAL_CONVERSATION_ID = "personal"
DEFAULT_MESSAGE_LIMIT = 80
MAX_MESSAGE_LIMIT = 300
DEFAULT_CONVERSATION_TITLE = "新对话"

_DB_LOCK = threading.RLock()
_EVENT_CONDITION = threading.Condition()
_EVENT_COUNTER = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def db_path(paths: RuntimePaths | None = None) -> Path:
    runtime_paths = paths or ensure_runtime_dirs()
    return runtime_paths.data_dir / DB_FILE_NAME


def _connect(paths: RuntimePaths | None = None) -> sqlite3.Connection:
    path = db_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            source TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
            ON messages(conversation_id, created_at, id);

        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            safe_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            summary_status TEXT NOT NULL,
            summary_text TEXT NOT NULL DEFAULT '',
            preview_data_url TEXT NOT NULL DEFAULT '',
            reason_cn TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attachments_message
            ON attachments(message_id);

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS approval_actions (
            id TEXT PRIMARY KEY,
            approval_id TEXT NOT NULL,
            status TEXT NOT NULL,
            operation TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_approval_actions_approval
            ON approval_actions(approval_id);
        """
    )
    conn.commit()


def ensure_schema(paths: RuntimePaths | None = None) -> None:
    with _DB_LOCK, _connect(paths) as conn:
        ensure_personal_conversation(paths, conn=conn)


def _json_loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def ensure_personal_conversation(
    paths: RuntimePaths | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    owns_conn = conn is None
    if conn is None:
        conn = _connect(paths)
    try:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (PERSONAL_CONVERSATION_ID,)).fetchone()
        if row is None:
            now = _now_iso()
            conn.execute(
                """
                INSERT INTO conversations(id, title, kind, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    PERSONAL_CONVERSATION_ID,
                    "个人会话",
                    "personal",
                    now,
                    now,
                    _json_dumps({"stable": True}),
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (PERSONAL_CONVERSATION_ID,)).fetchone()
        assert row is not None
        return _conversation_from_row(row)
    finally:
        if owns_conn:
            conn.close()


def _normalize_conversation_id(conversation_id: str | None) -> str:
    return (conversation_id or "").strip() or PERSONAL_CONVERSATION_ID


def _normalize_title(title: str | None, *, fallback: str = DEFAULT_CONVERSATION_TITLE) -> str:
    value = (title or "").strip()
    if not value:
        value = fallback
    return value[:80]


def _metadata_with_session(conversation_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    value = dict(metadata or {})
    value.setdefault("hermes_session_id", conversation_id)
    return value


def _is_archived(conversation: dict[str, Any]) -> bool:
    metadata = conversation.get("metadata") if isinstance(conversation.get("metadata"), dict) else {}
    return bool(metadata.get("archived_at"))


def create_conversation(
    *,
    title: str | None = None,
    kind: str = "desktop",
    metadata: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    paths: RuntimePaths | None = None,
    emit_event: bool = True,
) -> dict[str, Any]:
    conversation_id = _normalize_conversation_id(conversation_id) if conversation_id else _new_id("conv")
    now = _now_iso()
    with _DB_LOCK, _connect(paths) as conn:
        existing = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if existing is not None:
            return _conversation_from_row(existing)
        conn.execute(
            """
            INSERT INTO conversations(id, title, kind, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                _normalize_title(title),
                (kind or "desktop").strip() or "desktop",
                now,
                now,
                _json_dumps(_metadata_with_session(conversation_id, metadata)),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        assert row is not None
        conversation = _conversation_from_row(row)
    if emit_event:
        append_event("conversation.created", {"conversation": conversation, "conversation_id": conversation["id"]}, paths=paths)
    return conversation


def get_conversation(conversation_id: str, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    conversation_id = _normalize_conversation_id(conversation_id)
    with _DB_LOCK, _connect(paths) as conn:
        ensure_personal_conversation(paths, conn=conn)
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return _conversation_from_row(row) if row is not None else None


def ensure_conversation(
    conversation_id: str,
    *,
    title: str | None = None,
    kind: str = "desktop",
    metadata: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    conversation_id = _normalize_conversation_id(conversation_id)
    if conversation_id == PERSONAL_CONVERSATION_ID:
        return ensure_personal_conversation(paths, conn=conn)
    owns_conn = conn is None
    if conn is None:
        conn = _connect(paths)
    try:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            now = _now_iso()
            conn.execute(
                """
                INSERT INTO conversations(id, title, kind, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    _normalize_title(title),
                    (kind or "desktop").strip() or "desktop",
                    now,
                    now,
                    _json_dumps(_metadata_with_session(conversation_id, metadata)),
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        assert row is not None
        return _conversation_from_row(row)
    finally:
        if owns_conn:
            conn.close()


def _update_conversation_metadata(
    conn: sqlite3.Connection,
    conversation_id: str,
    updater,
) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if row is None:
        return None
    metadata = _json_loads(row["metadata"])
    next_metadata = updater(metadata) or metadata
    now = _now_iso()
    conn.execute(
        "UPDATE conversations SET metadata = ?, updated_at = ? WHERE id = ?",
        (_json_dumps(next_metadata), now, conversation_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return _conversation_from_row(row) if row is not None else None


def update_conversation(
    conversation_id: str,
    *,
    title: str | None = None,
    archived: bool | None = None,
    metadata_patch: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
    emit_event: bool = True,
) -> dict[str, Any] | None:
    conversation_id = _normalize_conversation_id(conversation_id)
    with _DB_LOCK, _connect(paths) as conn:
        ensure_personal_conversation(paths, conn=conn)
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        metadata = _json_loads(row["metadata"])
        if metadata_patch:
            metadata.update(metadata_patch)
        if archived is True and not metadata.get("archived_at"):
            metadata["archived_at"] = _now_iso()
        elif archived is False:
            metadata.pop("archived_at", None)
        next_title = _normalize_title(title, fallback=str(row["title"])) if title is not None else str(row["title"])
        now = _now_iso()
        conn.execute(
            "UPDATE conversations SET title = ?, metadata = ?, updated_at = ? WHERE id = ?",
            (next_title, _json_dumps(metadata), now, conversation_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        assert row is not None
        conversation = _conversation_from_row(row)
    if emit_event:
        append_event("conversation.updated", {"conversation": conversation, "conversation_id": conversation["id"]}, paths=paths)
    return conversation


def _conversation_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "kind": str(row["kind"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": _json_loads(row["metadata"]),
    }


def list_conversations(
    paths: RuntimePaths | None = None,
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    with _DB_LOCK, _connect(paths) as conn:
        ensure_personal_conversation(paths, conn=conn)
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC, id ASC"
        ).fetchall()
    conversations = [_conversation_from_row(row) for row in rows]
    if not include_archived:
        conversations = [item for item in conversations if not _is_archived(item)]
    return conversations


def delete_conversation(
    conversation_id: str,
    *,
    paths: RuntimePaths | None = None,
    emit_event: bool = True,
) -> dict[str, Any] | None:
    conversation_id = _normalize_conversation_id(conversation_id)
    with _DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        conversation = _conversation_from_row(row)
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
    if emit_event:
        append_event("conversation.deleted", {"conversation_id": conversation_id, "conversation": conversation}, paths=paths)
    return conversation


def hermes_session_id(conversation: dict[str, Any] | None, conversation_id: str | None = None) -> str:
    metadata = conversation.get("metadata") if conversation and isinstance(conversation.get("metadata"), dict) else {}
    value = str(metadata.get("hermes_session_id") or "").strip()
    return value or _normalize_conversation_id(conversation_id or (conversation or {}).get("id"))


def conversation_history_for_agent(
    conversation_id: str,
    *,
    exclude_message_id: str | None = None,
    paths: RuntimePaths | None = None,
    limit: int = MAX_MESSAGE_LIMIT,
) -> list[dict[str, str]]:
    messages = list_messages(conversation_id, limit=limit, paths=paths)
    history: list[dict[str, str]] = []
    for message in messages:
        if exclude_message_id and message.get("id") == exclude_message_id:
            continue
        role = str(message.get("role") or "")
        text = str(message.get("text") or "").strip()
        if role not in {"user", "assistant", "system"} or not text:
            continue
        history.append({"role": role, "content": text})
    return history


def maybe_set_title_from_message(
    conversation_id: str,
    text: str,
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    conversation = get_conversation(conversation_id, paths)
    if conversation is None:
        return None
    if conversation["id"] == PERSONAL_CONVERSATION_ID:
        return conversation
    title = str(conversation.get("title") or "").strip()
    if title not in {"", DEFAULT_CONVERSATION_TITLE, "新建对话"}:
        return conversation
    candidate = " ".join(text.strip().split())
    if not candidate:
        return conversation
    if len(candidate) > 28:
        candidate = f"{candidate[:28]}..."
    return update_conversation(conversation_id, title=candidate, paths=paths)


def _attachment_public_from_row(row: sqlite3.Row, *, include_safe_path: bool = False) -> dict[str, Any]:
    payload = {
        "id": str(row["id"]),
        "message_id": str(row["message_id"]),
        "conversation_id": str(row["conversation_id"]),
        "file_name": str(row["file_name"]),
        "mime_type": str(row["mime_type"]),
        "size_bytes": int(row["size_bytes"]),
        "summary_status": str(row["summary_status"]),
        "summary_text": str(row["summary_text"]),
        "preview_data_url": str(row["preview_data_url"]),
        "reason_cn": str(row["reason_cn"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": _json_loads(row["metadata"]),
    }
    if include_safe_path:
        payload["safe_path"] = str(row["safe_path"])
    return payload


def _message_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    attachments = conn.execute(
        "SELECT * FROM attachments WHERE message_id = ? ORDER BY created_at ASC, id ASC",
        (row["id"],),
    ).fetchall()
    return {
        "id": str(row["id"]),
        "conversation_id": str(row["conversation_id"]),
        "source": str(row["source"]),
        "role": str(row["role"]),
        "text": str(row["text"]),
        "attachments": [_attachment_public_from_row(item) for item in attachments],
        "created_at": str(row["created_at"]),
        "status": str(row["status"]),
        "metadata": _json_loads(row["metadata"]),
    }


def get_message(message_id: str, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    with _DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return None
        return _message_from_row(conn, row)


def list_messages(
    conversation_id: str,
    *,
    after_id: str | None = None,
    limit: int = DEFAULT_MESSAGE_LIMIT,
    paths: RuntimePaths | None = None,
) -> list[dict[str, Any]]:
    conversation_id = conversation_id.strip() or PERSONAL_CONVERSATION_ID
    limit = max(1, min(int(limit or DEFAULT_MESSAGE_LIMIT), MAX_MESSAGE_LIMIT))
    with _DB_LOCK, _connect(paths) as conn:
        ensure_personal_conversation(paths, conn=conn)
        if after_id:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                  AND rowid > COALESCE((SELECT rowid FROM messages WHERE id = ? AND conversation_id = ?), 0)
                ORDER BY rowid ASC
                LIMIT ?
                """,
                (conversation_id, after_id, conversation_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT rowid AS _rowid, * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY rowid DESC
                    LIMIT ?
                )
                ORDER BY _rowid ASC
                """,
                (conversation_id, limit),
            ).fetchall()
        return [_message_from_row(conn, row) for row in rows]


def create_message(
    *,
    conversation_id: str = PERSONAL_CONVERSATION_ID,
    source: str,
    role: str,
    text: str,
    status: str = "sent",
    metadata: dict[str, Any] | None = None,
    emit_event: bool = True,
    event_type: str = "message.created",
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    conversation_id = conversation_id.strip() or PERSONAL_CONVERSATION_ID
    message_id = _new_id("msg")
    now = _now_iso()
    with _DB_LOCK, _connect(paths) as conn:
        ensure_conversation(conversation_id, paths=paths, conn=conn)
        conn.execute(
            """
            INSERT INTO messages(id, conversation_id, source, role, text, created_at, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                source.strip() or "local",
                role.strip() or "user",
                text,
                now,
                status.strip() or "sent",
                _json_dumps(metadata or {}),
            ),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        assert row is not None
        message = _message_from_row(conn, row)
        if role.strip() == "user":
            current = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if current is not None:
                current_conversation = _conversation_from_row(current)
                title = str(current_conversation.get("title") or "").strip()
                if conversation_id != PERSONAL_CONVERSATION_ID and title in {"", DEFAULT_CONVERSATION_TITLE, "新建对话"}:
                    candidate = " ".join(text.strip().split())
                    if candidate:
                        if len(candidate) > 28:
                            candidate = f"{candidate[:28]}..."
                        conn.execute(
                            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                            (candidate, now, conversation_id),
                        )
                        conn.commit()
    if emit_event:
        append_event(event_type, {"conversation_id": conversation_id, "message": message}, paths=paths)
    return message


def record_message_event(
    message_id: str,
    *,
    event_type: str = "message.created",
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    message = get_message(message_id, paths)
    if message is None:
        return None
    append_event(event_type, {"conversation_id": message["conversation_id"], "message": message}, paths=paths)
    return message


def create_system_message(
    text: str,
    *,
    conversation_id: str = PERSONAL_CONVERSATION_ID,
    metadata: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    return create_message(
        conversation_id=conversation_id,
        source="system",
        role="system",
        text=text,
        status="sent",
        metadata=metadata,
        paths=paths,
    )


def create_attachment_record(
    *,
    attachment_id: str | None = None,
    message_id: str,
    conversation_id: str,
    safe_path: Path,
    file_name: str,
    mime_type: str,
    size_bytes: int,
    summary_status: str,
    summary_text: str = "",
    preview_data_url: str = "",
    reason_cn: str = "",
    metadata: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    attachment_id = attachment_id or _new_id("att")
    now = _now_iso()
    with _DB_LOCK, _connect(paths) as conn:
        conn.execute(
            """
            INSERT INTO attachments(
                id, message_id, conversation_id, safe_path, file_name, mime_type, size_bytes,
                summary_status, summary_text, preview_data_url, reason_cn, created_at, updated_at, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_id,
                message_id,
                conversation_id,
                str(safe_path),
                file_name,
                mime_type,
                int(size_bytes),
                summary_status,
                summary_text,
                preview_data_url,
                reason_cn,
                now,
                now,
                _json_dumps(metadata or {}),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        assert row is not None
        attachment = _attachment_public_from_row(row)
    append_event(
        "attachment_registered",
        {"conversation_id": conversation_id, "message_id": message_id, "attachment": attachment},
        paths=paths,
    )
    return attachment


def update_attachment_summary(
    attachment_id: str,
    *,
    summary_status: str,
    summary_text: str = "",
    preview_data_url: str = "",
    reason_cn: str = "",
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    now = _now_iso()
    with _DB_LOCK, _connect(paths) as conn:
        conn.execute(
            """
            UPDATE attachments
            SET summary_status = ?, summary_text = ?, preview_data_url = ?, reason_cn = ?, updated_at = ?
            WHERE id = ?
            """,
            (summary_status, summary_text, preview_data_url, reason_cn, now, attachment_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        if row is None:
            return None
        attachment = _attachment_public_from_row(row)
    append_event(
        "attachment_summary_updated",
        {
            "conversation_id": attachment["conversation_id"],
            "message_id": attachment["message_id"],
            "attachment": attachment,
        },
        paths=paths,
    )
    return attachment


def get_attachment(
    attachment_id: str,
    *,
    include_safe_path: bool = False,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    with _DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        if row is None:
            return None
        return _attachment_public_from_row(row, include_safe_path=include_safe_path)


def list_recent_attachments(
    *,
    limit: int = 20,
    include_safe_path: bool = False,
    paths: RuntimePaths | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 20), 100))
    with _DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            """
            SELECT a.*, m.source AS message_source, m.role AS message_role
            FROM attachments a
            JOIN messages m ON m.id = a.message_id
            WHERE a.conversation_id = ?
            ORDER BY a.rowid DESC
            LIMIT ?
            """,
            (PERSONAL_CONVERSATION_ID, limit),
        ).fetchall()
    attachments = []
    for row in rows:
        attachment = _attachment_public_from_row(row, include_safe_path=include_safe_path)
        attachment["message_source"] = str(row["message_source"])
        attachment["message_role"] = str(row["message_role"])
        attachments.append(attachment)
    return attachments


def find_recent_generated_attachment(
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    for attachment in list_recent_attachments(limit=40, paths=paths):
        metadata = attachment.get("metadata") if isinstance(attachment.get("metadata"), dict) else {}
        source = str(metadata.get("source") or "")
        message_role = str(attachment.get("message_role") or "")
        message_source = str(attachment.get("message_source") or "")
        if source == "generated" or (message_role in {"assistant", "system"} and message_source != "weixin"):
            attachment.pop("message_source", None)
            attachment.pop("message_role", None)
            return attachment
    return None


def weixin_route_key(route: dict[str, Any] | None) -> str:
    route = route or {}
    account_id = str(route.get("account_id") or "").strip()
    chat_type = str(route.get("chat_type") or "dm").strip() or "dm"
    chat_id = str(route.get("chat_id") or "").strip()
    user_id = str(route.get("user_id") or "").strip()
    identity = chat_id or user_id
    if not identity:
        return ""
    if account_id:
        return f"{account_id}:{chat_type}:{identity}"
    return f"{chat_type}:{identity}"


def _weixin_route_metadata(route: dict[str, Any]) -> dict[str, Any]:
    metadata_route: dict[str, str] = {
        "chat_type": str(route.get("chat_type") or "dm").strip() or "dm",
    }
    account_id = str(route.get("account_id") or "").strip()
    chat_id = str(route.get("chat_id") or "").strip()
    user_id = str(route.get("user_id") or "").strip()
    if account_id:
        metadata_route["account_id"] = account_id
    if chat_id:
        metadata_route["chat_id"] = chat_id
    if user_id:
        metadata_route["user_id"] = user_id
    return metadata_route


def _deactivate_weixin_route(
    conn: sqlite3.Connection,
    route_key: str,
    *,
    except_conversation_id: str | None = None,
) -> None:
    rows = conn.execute("SELECT * FROM conversations WHERE kind = 'weixin'").fetchall()
    now = _now_iso()
    for row in rows:
        conversation_id = str(row["id"])
        if except_conversation_id and conversation_id == except_conversation_id:
            continue
        metadata = _json_loads(row["metadata"])
        if metadata.get("weixin_route_key") != route_key:
            continue
        if not metadata.get("weixin_route_active"):
            continue
        metadata["weixin_route_active"] = False
        conn.execute(
            "UPDATE conversations SET metadata = ?, updated_at = ? WHERE id = ?",
            (_json_dumps(metadata), now, conversation_id),
        )


def create_weixin_conversation(
    route: dict[str, Any],
    *,
    title: str | None = None,
    paths: RuntimePaths | None = None,
    emit_event: bool = True,
) -> dict[str, Any]:
    route_metadata = _weixin_route_metadata(route)
    route_key = weixin_route_key(route_metadata)
    if not route_key:
        return create_conversation(title=title or "微信私聊", kind="weixin", paths=paths, emit_event=emit_event)
    conversation_id = _new_id("conv")
    now = _now_iso()
    metadata = _metadata_with_session(
        conversation_id,
        {
            "weixin_route": route_metadata,
            "weixin_route_key": route_key,
            "weixin_route_active": True,
        },
    )
    with _DB_LOCK, _connect(paths) as conn:
        _deactivate_weixin_route(conn, route_key)
        conn.execute(
            """
            INSERT INTO conversations(id, title, kind, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                _normalize_title(title, fallback="微信私聊"),
                "weixin",
                now,
                now,
                _json_dumps(metadata),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        assert row is not None
        conversation = _conversation_from_row(row)
    if emit_event:
        append_event("conversation.created", {"conversation": conversation, "conversation_id": conversation_id}, paths=paths)
    return conversation


def active_weixin_conversation(
    route: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    route_key = weixin_route_key(route)
    if not route_key:
        return None
    for conversation in list_conversations(paths, include_archived=True):
        if conversation.get("kind") != "weixin" or _is_archived(conversation):
            continue
        metadata = conversation.get("metadata") if isinstance(conversation.get("metadata"), dict) else {}
        if metadata.get("weixin_route_key") == route_key and metadata.get("weixin_route_active"):
            return conversation
    return None


def ensure_active_weixin_conversation(
    route: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    active = active_weixin_conversation(route, paths=paths)
    if active is not None:
        return active
    return create_weixin_conversation(route, paths=paths)


def set_weixin_conversation_active(
    conversation_id: str,
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    conversation_id = _normalize_conversation_id(conversation_id)
    with _DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        metadata = _json_loads(row["metadata"])
        route_key = str(metadata.get("weixin_route_key") or "").strip()
        if str(row["kind"]) != "weixin" or not route_key:
            return None
        _deactivate_weixin_route(conn, route_key, except_conversation_id=conversation_id)
        metadata["weixin_route_active"] = True
        metadata.pop("archived_at", None)
        now = _now_iso()
        conn.execute(
            "UPDATE conversations SET metadata = ?, updated_at = ? WHERE id = ?",
            (_json_dumps(metadata), now, conversation_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        assert row is not None
        conversation = _conversation_from_row(row)
    append_event("conversation.updated", {"conversation": conversation, "conversation_id": conversation_id}, paths=paths)
    return conversation


def latest_weixin_route(
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, str] | None:
    with _DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            """
            SELECT metadata
            FROM messages
            WHERE source = 'weixin' AND role = 'user'
            ORDER BY rowid DESC
            LIMIT 20
            """,
        ).fetchall()
    for row in rows:
        metadata = _json_loads(row["metadata"])
        route = metadata.get("weixin_route") if isinstance(metadata.get("weixin_route"), dict) else None
        if not route:
            continue
        chat_id = str(route.get("chat_id") or "").strip()
        user_id = str(route.get("user_id") or "").strip()
        if chat_id or user_id:
            latest_route = {
                "chat_id": chat_id,
                "user_id": user_id,
                "chat_type": str(route.get("chat_type") or "dm").strip() or "dm",
            }
            account_id = str(route.get("account_id") or "").strip()
            if account_id:
                latest_route["account_id"] = account_id
            return latest_route
    return None


def record_approval_action(
    approval: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
) -> None:
    approval_id = str(approval.get("id") or "").strip()
    if not approval_id:
        return
    status = str(approval.get("status") or "pending")
    operation = str(approval.get("operation") or "")
    now = _now_iso()
    payload = _json_dumps(approval)
    with _DB_LOCK, _connect(paths) as conn:
        existing = conn.execute(
            "SELECT id FROM approval_actions WHERE approval_id = ? ORDER BY created_at DESC LIMIT 1",
            (approval_id,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO approval_actions(id, approval_id, status, operation, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (_new_id("approval_action"), approval_id, status, operation, payload, now, now),
            )
        else:
            conn.execute(
                """
                UPDATE approval_actions
                SET status = ?, operation = ?, payload = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, operation, payload, now, existing["id"]),
            )
        conn.commit()
    append_event("approval.updated", {"approval": approval}, paths=paths)


def append_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    with _DB_LOCK, _connect(paths) as conn:
        now = _now_iso()
        cursor = conn.execute(
            "INSERT INTO events(event_type, payload, created_at) VALUES (?, ?, ?)",
            (event_type, _json_dumps(payload), now),
        )
        event_id = int(cursor.lastrowid)
        conn.commit()
    event = {"id": event_id, "event": event_type, "data": payload, "created_at": now}
    _notify_event_waiters()
    return event


def list_events_after(
    after_id: int,
    *,
    limit: int = 100,
    paths: RuntimePaths | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 500))
    with _DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (max(0, int(after_id or 0)), limit),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "event": str(row["event_type"]),
            "data": _json_loads(row["payload"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def format_sse_event(event: dict[str, Any]) -> str:
    payload = json.dumps(event.get("data") or {}, ensure_ascii=False, separators=(",", ":"))
    return f"id: {int(event['id'])}\nevent: {event['event']}\ndata: {payload}\n\n"


async def wait_for_events_after(
    after_id: int,
    *,
    timeout_seconds: float = 15.0,
    paths: RuntimePaths | None = None,
) -> list[dict[str, Any]]:
    events = list_events_after(after_id, paths=paths)
    if events:
        return events

    snapshot = _event_snapshot()
    events = list_events_after(after_id, paths=paths)
    if events:
        return events

    await asyncio.to_thread(_wait_for_event, snapshot, timeout_seconds)
    return list_events_after(after_id, paths=paths)


def _event_snapshot() -> int:
    with _EVENT_CONDITION:
        return _EVENT_COUNTER


def _wait_for_event(snapshot: int, timeout_seconds: float) -> None:
    with _EVENT_CONDITION:
        if _EVENT_COUNTER == snapshot:
            _EVENT_CONDITION.wait(timeout=max(0.1, timeout_seconds))


def _notify_event_waiters() -> None:
    global _EVENT_COUNTER
    with _EVENT_CONDITION:
        _EVENT_COUNTER += 1
        _EVENT_CONDITION.notify_all()
