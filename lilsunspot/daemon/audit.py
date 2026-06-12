from __future__ import annotations

import json
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import RuntimePaths, ensure_runtime_dirs


AUDIT_DB_NAME = "audit.db"
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bot_token",
    "credential",
    "password",
    "refresh_token",
    "runtime_token",
    "secret",
    "token",
}
SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"(?i)(\bBearer\s+)([A-Za-z0-9._~+/=-]+)"),
    re.compile(
        r"(?i)(--?(?:api[-_]?key|token|secret|password|authorization|credential|bot[-_]?token|refresh[-_]?token|access[-_]?token)(?:=|\s+))([^\s]+)"
    ),
    re.compile(r"(?i)([?&](?:api_key|apikey|token|secret|password|access_token|refresh_token)=)([^&\s]+)"),
    re.compile(
        r"(?i)\b((?:api[-_]?key|token|secret|password|authorization|credential|bot[-_]?token|refresh[-_]?token|access[-_]?token)\s*[:=]\s*)([^\s,;&]+)"
    ),
]
SENSITIVE_STANDALONE_FLAG = re.compile(
    r"(?i)^-{1,2}(?:api[-_]?key|token|secret|password|authorization|credential|bot[-_]?token|refresh[-_]?token|access[-_]?token)$"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_db_path(paths: RuntimePaths | None = None) -> Path:
    runtime_paths = paths or ensure_runtime_dirs()
    return runtime_paths.data_dir / AUDIT_DB_NAME


def ensure_audit_schema(paths: RuntimePaths | None = None) -> Path:
    db_path = audit_db_path(paths)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_events(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type)")
    return db_path


def _runtime_token() -> str:
    try:
        from .auth import load_or_create_token

        return load_or_create_token()
    except Exception:
        return ""


def redact_text(value: str, token: str = "") -> str:
    text = value
    if token:
        text = text.replace(token, "[已隐藏]")
    for pattern in SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub(r"\1[已隐藏]", text)
    return text


def redact_value(value: Any) -> Any:
    token = _runtime_token()

    def _redact(item: Any) -> Any:
        if isinstance(item, dict):
            redacted: dict[str, Any] = {}
            for key, child in item.items():
                key_text = str(key)
                lowered = key_text.lower()
                if any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
                    redacted[key_text] = "[已隐藏]"
                else:
                    redacted[key_text] = _redact(child)
            return redacted
        if isinstance(item, list):
            redacted_items: list[Any] = []
            redact_next = False
            for child in item:
                if redact_next and isinstance(child, str):
                    redacted_items.append("[已隐藏]")
                    redact_next = False
                    continue
                redacted_items.append(_redact(child))
                redact_next = isinstance(child, str) and bool(SENSITIVE_STANDALONE_FLAG.fullmatch(child.strip()))
            return redacted_items
        if isinstance(item, str):
            return redact_text(item, token)
        return item

    return _redact(value)


def record_audit_event(
    event_type: str,
    summary: str,
    *,
    source: str = "lilsunspot",
    status: str = "ok",
    details: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    ensure_audit_schema(paths)
    event = {
        "event_id": f"audit_{secrets.token_hex(8)}",
        "event_type": (event_type or "event").strip(),
        "source": (source or "lilsunspot").strip(),
        "status": (status or "ok").strip(),
        "summary": str(redact_value(summary or event_type or "审计事件")),
        "details": redact_value(details or {}),
        "created_at": _now_iso(),
    }
    with sqlite3.connect(audit_db_path(paths)) as conn:
        conn.execute(
            """
            INSERT INTO audit_events
                (event_id, event_type, source, status, summary, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["event_type"],
                event["source"],
                event["status"],
                event["summary"],
                json.dumps(event["details"], ensure_ascii=False, sort_keys=True),
                event["created_at"],
            ),
        )
    return public_audit_event(event)


def public_audit_event(event: dict[str, Any]) -> dict[str, Any]:
    public = dict(event)
    public["details"] = redact_value(public.get("details") if isinstance(public.get("details"), dict) else {})
    return public


def list_audit_events(limit: int = 100, paths: RuntimePaths | None = None) -> dict[str, Any]:
    ensure_audit_schema(paths)
    safe_limit = max(1, min(int(limit or 100), 500))
    rows: list[sqlite3.Row]
    with sqlite3.connect(audit_db_path(paths)) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                """
                SELECT event_id, event_type, source, status, summary, details_json, created_at
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
        )
    events = []
    for row in rows:
        try:
            details = json.loads(str(row["details_json"] or "{}"))
        except json.JSONDecodeError:
            details = {}
        events.append(
            public_audit_event(
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "source": row["source"],
                    "status": row["status"],
                    "summary": row["summary"],
                    "details": details if isinstance(details, dict) else {},
                    "created_at": row["created_at"],
                }
            )
        )
    return {"events": events, "audit_db": str(audit_db_path(paths)), "limit": safe_limit}
