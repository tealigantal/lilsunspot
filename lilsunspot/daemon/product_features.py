from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import conversations
from .attachments import AttachmentError, is_safe_stored_attachment
from .capability_graph import build_capability_graph, graph_node
from .chat_client import current_runtime_model, image_recognition_status
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .doctor import run_doctor_checks
from .gateway import weixin_status
from .hermes_runtime import read_hermes_config
from .providers import provider_by_id
from .runtime_discovery import read_runtime_descriptor
from .upstream_audit import safe_upstream_capability_audit


DEFAULT_CAPABILITIES = [
    {
        "id": "web_search",
        "label": "联网搜索",
        "description": "后续接入 Hermes 搜索工具时用于允许联网查询。",
        "enabled": False,
        "requires_approval": False,
    },
    {
        "id": "file_read",
        "label": "读取本地文件",
        "description": "允许小黑子读取用户明确选择的本地文件。",
        "enabled": True,
        "requires_approval": False,
    },
    {
        "id": "image_generation",
        "label": "生成图片",
        "description": "后续接入 Hermes 图片生成工具时使用。",
        "enabled": False,
        "requires_approval": True,
    },
    {
        "id": "reminders",
        "label": "提醒和自动任务",
        "description": "允许保存本地提醒，并由小黑子后台执行一次性或每日任务。",
        "enabled": True,
        "requires_approval": False,
    },
    {
        "id": "weixin_send",
        "label": "微信主动发送",
        "description": "允许创建微信发送审批；真正发送仍需要安全确认。",
        "enabled": True,
        "requires_approval": True,
    },
]

TASK_SCHEDULES = {"once", "daily"}
TASK_KINDS = {"reminder", "daily_summary", "check"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


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


def _local_timezone():
    return datetime.now().astimezone().tzinfo or timezone.utc


def _parse_task_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_timezone())
    return parsed


def _normalize_task_due_at(value: str) -> str:
    parsed = _parse_task_datetime(value)
    if parsed is None:
        raise ValueError("任务时间需要使用明确的日期和时间。")
    return parsed.astimezone(_local_timezone()).isoformat(timespec="minutes")


def _normalize_task_schedule(value: str | None) -> str:
    schedule = (value or "once").strip().lower() or "once"
    if schedule not in TASK_SCHEDULES:
        raise ValueError("任务计划只支持一次或每天。")
    return schedule


def _normalize_task_kind(value: str | None) -> str:
    kind = (value or "reminder").strip().lower() or "reminder"
    if kind not in TASK_KINDS:
        raise ValueError("任务类型只支持提醒、定时总结或定时检查。")
    return kind


def _task_due_at_is_due(value: str, now: datetime) -> bool:
    due_at = _parse_task_datetime(value)
    if due_at is None:
        return False
    return due_at.astimezone(timezone.utc) <= now.astimezone(timezone.utc)


def _next_daily_due_at(value: str, now: datetime) -> str:
    due_at = _parse_task_datetime(value)
    if due_at is None:
        raise ValueError("任务时间需要使用明确的日期和时间。")
    next_due = due_at.astimezone(_local_timezone())
    local_now = now.astimezone(_local_timezone())
    while next_due <= local_now:
        next_due = next_due + timedelta(days=1)
    return next_due.isoformat(timespec="minutes")


def _connect(paths: RuntimePaths | None = None) -> sqlite3.Connection:
    conn = conversations._connect(paths)  # Product tables share the local conversation database.
    ensure_schema_for_connection(conn)
    return conn


def ensure_schema(paths: RuntimePaths | None = None) -> None:
    with conversations._DB_LOCK, conversations._connect(paths) as conn:
        ensure_schema_for_connection(conn)


def ensure_schema_for_connection(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS product_reminders (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            prompt TEXT NOT NULL,
            due_at TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            completed_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS product_memories (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            source TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS product_capabilities (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            requires_approval INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS product_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            instructions TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );
        """
    )
    now = _now_iso()
    for capability in DEFAULT_CAPABILITIES:
        conn.execute(
            """
            INSERT OR IGNORE INTO product_capabilities(
                id, label, description, enabled, requires_approval, created_at, updated_at, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capability["id"],
                capability["label"],
                capability["description"],
                1 if capability["enabled"] else 0,
                1 if capability["requires_approval"] else 0,
                now,
                now,
                _json_dumps({"source": "hermes_merge_plan"}),
            ),
        )
    conn.commit()


def _reminder_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "prompt": str(row["prompt"]),
        "due_at": str(row["due_at"]),
        "enabled": bool(row["enabled"]),
        "completed_at": str(row["completed_at"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": _json_loads(row["metadata"]),
    }


def list_reminders(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    with conversations._DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            "SELECT * FROM product_reminders ORDER BY enabled DESC, due_at ASC, created_at DESC"
        ).fetchall()
    return [_reminder_from_row(row) for row in rows]


def create_reminder(
    *,
    title: str,
    prompt: str,
    due_at: str = "",
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    title = " ".join((title or "").split())[:80]
    prompt = " ".join((prompt or "").split())[:1000]
    due_at = (due_at or "").strip()[:80]
    if not title:
        raise ValueError("提醒标题不能为空。")
    if not prompt:
        raise ValueError("提醒内容不能为空。")
    reminder_id = _new_id("rem")
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        conn.execute(
            """
            INSERT INTO product_reminders(id, title, prompt, due_at, enabled, completed_at, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, 1, '', ?, ?, ?)
            """,
            (reminder_id, title, prompt, due_at, now, now, _json_dumps({"source": "desktop"})),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (reminder_id,)).fetchone()
        assert row is not None
        return _reminder_from_row(row)


def update_reminder(
    reminder_id: str,
    *,
    enabled: bool | None = None,
    completed: bool | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (reminder_id,)).fetchone()
        if row is None:
            return None
        next_enabled = bool(row["enabled"]) if enabled is None else bool(enabled)
        completed_at = str(row["completed_at"])
        if completed is True:
            next_enabled = False
            completed_at = now
        elif completed is False:
            completed_at = ""
        conn.execute(
            "UPDATE product_reminders SET enabled = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (1 if next_enabled else 0, completed_at, now, reminder_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (reminder_id,)).fetchone()
        assert row is not None
        return _reminder_from_row(row)


def delete_reminder(reminder_id: str, paths: RuntimePaths | None = None) -> bool:
    with conversations._DB_LOCK, _connect(paths) as conn:
        cursor = conn.execute("DELETE FROM product_reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        return cursor.rowcount > 0


def _task_status(reminder: dict[str, Any]) -> str:
    if reminder["completed_at"]:
        return "completed"
    if reminder["enabled"]:
        return "active"
    return "paused"


def _task_from_reminder_row(row: sqlite3.Row) -> dict[str, Any]:
    reminder = _reminder_from_row(row)
    metadata = reminder["metadata"] if isinstance(reminder.get("metadata"), dict) else {}
    run_history = metadata.get("run_history")
    if not isinstance(run_history, list):
        run_history = []
    status = _task_status(reminder)
    due_at = reminder["due_at"]
    schedule = str(metadata.get("schedule") or "once")
    scheduler = str(metadata.get("scheduler") or "manual")
    schedule_parseable = _parse_task_datetime(due_at) is not None if due_at else False
    return {
        "id": reminder["id"],
        "title": reminder["title"],
        "prompt": reminder["prompt"],
        "kind": str(metadata.get("kind") or "reminder"),
        "schedule": schedule,
        "status": status,
        "enabled": reminder["enabled"],
        "completed_at": reminder["completed_at"],
        "next_run_at": due_at if status == "active" and schedule_parseable else "",
        "due_at": due_at,
        "last_run_at": str(metadata.get("last_run_at") or ""),
        "last_result": str(metadata.get("last_result") or ""),
        "last_error": str(metadata.get("last_error") or ""),
        "run_history": run_history[-10:],
        "created_at": reminder["created_at"],
        "updated_at": reminder["updated_at"],
        "metadata": {
            "source": metadata.get("source") or "desktop",
            "delivery": metadata.get("delivery") or "local_only",
            "scheduler": scheduler,
            "schedule": schedule,
            "timezone": metadata.get("timezone") or str(_local_timezone()),
            "schedule_parseable": schedule_parseable,
            "last_run_trigger": metadata.get("last_run_trigger") or "",
        },
    }


def list_tasks(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    with conversations._DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            "SELECT * FROM product_reminders ORDER BY enabled DESC, due_at ASC, updated_at DESC"
        ).fetchall()
    return [_task_from_reminder_row(row) for row in rows]


def create_task(
    *,
    title: str,
    prompt: str,
    due_at: str = "",
    kind: str = "reminder",
    schedule: str = "once",
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    title = " ".join((title or "").split())[:80]
    prompt = " ".join((prompt or "").split())[:1000]
    due_at = _normalize_task_due_at(due_at)
    kind = _normalize_task_kind(kind)
    schedule = _normalize_task_schedule(schedule)
    if not title:
        raise ValueError("任务标题不能为空。")
    if not prompt:
        raise ValueError("任务内容不能为空。")
    task_id = _new_id("task")
    now = _now_iso()
    metadata = {
        "source": "desktop",
        "kind": kind,
        "delivery": "local_only",
        "scheduler": "background",
        "schedule": schedule,
        "timezone": str(_local_timezone()),
        "run_history": [],
    }
    with conversations._DB_LOCK, _connect(paths) as conn:
        conn.execute(
            """
            INSERT INTO product_reminders(id, title, prompt, due_at, enabled, completed_at, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, 1, '', ?, ?, ?)
            """,
            (task_id, title, prompt, due_at, now, now, _json_dumps(metadata)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        assert row is not None
        return _task_from_reminder_row(row)


def update_task(
    task_id: str,
    *,
    title: str | None = None,
    prompt: str | None = None,
    due_at: str | None = None,
    kind: str | None = None,
    schedule: str | None = None,
    enabled: bool | None = None,
    completed: bool | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        metadata = _json_loads(row["metadata"])
        if kind is not None:
            metadata["kind"] = _normalize_task_kind(kind)
        if schedule is not None:
            metadata["schedule"] = _normalize_task_schedule(schedule)
        metadata["scheduler"] = "background"
        metadata.setdefault("timezone", str(_local_timezone()))
        next_title = str(row["title"]) if title is None else " ".join(title.split())[:80]
        next_prompt = str(row["prompt"]) if prompt is None else " ".join(prompt.split())[:1000]
        next_due_at = str(row["due_at"]) if due_at is None else _normalize_task_due_at(due_at)
        if not next_title:
            raise ValueError("任务标题不能为空。")
        if not next_prompt:
            raise ValueError("任务内容不能为空。")
        next_enabled = bool(row["enabled"]) if enabled is None else bool(enabled)
        completed_at = str(row["completed_at"])
        if completed is True:
            next_enabled = False
            completed_at = now
        elif completed is False:
            completed_at = ""
        conn.execute(
            """
            UPDATE product_reminders
            SET title = ?, prompt = ?, due_at = ?, enabled = ?, completed_at = ?, updated_at = ?, metadata = ?
            WHERE id = ?
            """,
            (next_title, next_prompt, next_due_at, 1 if next_enabled else 0, completed_at, now, _json_dumps(metadata), task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        assert row is not None
        return _task_from_reminder_row(row)


def _task_kind_label(kind: str) -> str:
    if kind == "daily_summary":
        return "定时总结"
    if kind == "check":
        return "定时检查"
    return "提醒"


def _build_task_message(task: dict[str, Any], *, paths: RuntimePaths) -> tuple[str, dict[str, Any]]:
    title = str(task.get("title") or "任务")
    prompt = str(task.get("prompt") or "")
    kind = str(task.get("kind") or "reminder")
    if kind == "daily_summary":
        summary = usage_summary(paths)
        text = (
            f"定时总结：{title}\n"
            f"{prompt}\n\n"
            f"本地概览：会话 {summary['conversations']['total']} 个，消息 {summary['messages']['total']} 条，"
            f"启用任务 {summary['tasks']['active']} 个，错误消息 {summary['messages']['errors']} 条。"
        )
        return text, {"usage": summary}
    if kind == "check":
        diagnostics = diagnostics_summary(paths)
        text = (
            f"定时检查：{title}\n"
            f"{prompt}\n\n"
            f"当前状态：模型 {'已配置' if diagnostics['model']['configured'] else '未配置'}，"
            f"微信 {'已连接' if diagnostics['weixin']['connected'] else '未连接'}，"
            f"本地服务 {'正常' if diagnostics['local_service']['doctor_ok'] else '需要检查'}。"
        )
        return text, {"diagnostics": diagnostics}
    return f"任务提醒：{title}\n{prompt}", {}


def _execute_task(task: dict[str, Any], *, trigger: str, paths: RuntimePaths) -> dict[str, Any]:
    text, details = _build_task_message(task, paths=paths)
    message = conversations.create_system_message(
        text,
        conversation_id=conversations.PERSONAL_CONVERSATION_ID,
        metadata={
            "kind": "task.run",
            "task_id": task["id"],
            "task_kind": task.get("kind") or "reminder",
            "trigger": trigger,
        },
        paths=paths,
    )
    return {
        "state": "succeeded",
        "message": f"{_task_kind_label(str(task.get('kind') or 'reminder'))}已写入聊天。",
        "conversation_id": conversations.PERSONAL_CONVERSATION_ID,
        "message_id": message["id"],
        "details": details,
    }


def _record_task_run(
    task_id: str,
    *,
    entry: dict[str, Any],
    trigger: str,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    now = str(entry.get("ran_at") or _now_iso())
    with conversations._DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        metadata = _json_loads(row["metadata"])
        history = metadata.get("run_history")
        if not isinstance(history, list):
            history = []
        history.append(entry)
        state = str(entry.get("state") or "")
        completed_at = str(row["completed_at"])
        next_enabled = bool(row["enabled"])
        next_due_at = str(row["due_at"])
        if trigger == "scheduled" and state == "succeeded":
            schedule = str(metadata.get("schedule") or "once")
            if schedule == "daily":
                next_due_at = _next_daily_due_at(next_due_at, datetime.now(timezone.utc))
                completed_at = ""
                next_enabled = True
            else:
                next_enabled = False
                completed_at = now
        metadata.update(
            {
                "last_run_at": now,
                "last_result": str(entry.get("message") or ""),
                "last_error": "" if state == "succeeded" else str(entry.get("message") or "任务运行失败。"),
                "run_history": history[-10:],
                "scheduler": "background",
                "last_run_trigger": trigger,
            }
        )
        conn.execute(
            """
            UPDATE product_reminders
            SET due_at = ?, enabled = ?, completed_at = ?, updated_at = ?, metadata = ?
            WHERE id = ?
            """,
            (next_due_at, 1 if next_enabled else 0, completed_at, now, _json_dumps(metadata), task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        assert row is not None
        task = _task_from_reminder_row(row)
    conversations.append_event("task.run.finished", {"task": task, "task_id": task_id, "run": entry}, paths=paths)
    return {"task": task, "run": task["run_history"][-1] if task["run_history"] else entry}


def run_task(task_id: str, paths: RuntimePaths | None = None, *, trigger: str = "manual") -> dict[str, Any] | None:
    runtime_paths = paths or ensure_runtime_dirs()
    with conversations._DB_LOCK, _connect(runtime_paths) as conn:
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        task = _task_from_reminder_row(row)
    ran_at = _now_iso()
    try:
        result = _execute_task(task, trigger=trigger, paths=runtime_paths)
        entry = {"ran_at": ran_at, "trigger": trigger, **result}
    except Exception as exc:  # pragma: no cover - defensive safety record
        entry = {
            "ran_at": ran_at,
            "trigger": trigger,
            "state": "failed",
            "message": f"任务运行失败：{exc}",
        }
    return _record_task_run(task_id, entry=entry, trigger=trigger, paths=runtime_paths)


def _mark_task_schedule_error(task_id: str, message: str, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        metadata = _json_loads(row["metadata"])
        history = metadata.get("run_history")
        if not isinstance(history, list):
            history = []
        entry = {"ran_at": now, "trigger": "scheduled", "state": "failed", "message": message}
        history.append(entry)
        metadata.update(
            {
                "last_run_at": now,
                "last_result": "",
                "last_error": message,
                "run_history": history[-10:],
                "scheduler": "background",
                "last_run_trigger": "scheduled",
            }
        )
        conn.execute(
            "UPDATE product_reminders SET enabled = 0, updated_at = ?, metadata = ? WHERE id = ?",
            (now, _json_dumps(metadata), task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_reminders WHERE id = ?", (task_id,)).fetchone()
        assert row is not None
        task = _task_from_reminder_row(row)
    conversations.append_event("task.run.failed", {"task": task, "task_id": task_id, "run": entry}, paths=paths)
    return {"task": task, "run": entry}


def run_due_tasks(
    paths: RuntimePaths | None = None,
    *,
    now: datetime | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    runtime_paths = paths or ensure_runtime_dirs()
    now_dt = now or datetime.now(timezone.utc)
    limit = max(1, min(int(limit or 10), 50))
    due_task_ids: list[str] = []
    invalid_task_ids: list[str] = []
    with conversations._DB_LOCK, _connect(runtime_paths) as conn:
        rows = conn.execute(
            """
            SELECT * FROM product_reminders
            WHERE enabled = 1 AND completed_at = ''
            ORDER BY due_at ASC, updated_at ASC
            LIMIT 100
            """
        ).fetchall()
        for row in rows:
            metadata = _json_loads(row["metadata"])
            if str(metadata.get("scheduler") or "") != "background":
                continue
            due_at = str(row["due_at"] or "")
            if not due_at:
                continue
            if _parse_task_datetime(due_at) is None:
                invalid_task_ids.append(str(row["id"]))
                continue
            if _task_due_at_is_due(due_at, now_dt):
                due_task_ids.append(str(row["id"]))
            if len(due_task_ids) >= limit:
                break
    results: list[dict[str, Any]] = []
    for task_id in invalid_task_ids:
        result = _mark_task_schedule_error(task_id, "任务时间无法识别，已暂停。", paths=runtime_paths)
        if result is not None:
            results.append(result)
    for task_id in due_task_ids[:limit]:
        result = run_task(task_id, paths=runtime_paths, trigger="scheduled")
        if result is not None:
            results.append(result)
    return results


def _memory_from_row(row: sqlite3.Row) -> dict[str, Any]:
    metadata = _json_loads(row["metadata"])
    metadata.setdefault("memory_scope", "local_record")
    metadata.setdefault("scope_label", "本地记录")
    metadata.setdefault("agent_memory_synced", False)
    return {
        "id": str(row["id"]),
        "text": str(row["text"]),
        "source": str(row["source"]),
        "enabled": bool(row["enabled"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": metadata,
        "memory_scope": "local_record",
        "scope_label": "本地记录",
        "agent_memory_synced": False,
    }


def list_memories(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    with conversations._DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            "SELECT * FROM product_memories ORDER BY enabled DESC, updated_at DESC, id ASC"
        ).fetchall()
    return [_memory_from_row(row) for row in rows]


def create_memory(*, text: str, source: str = "manual", paths: RuntimePaths | None = None) -> dict[str, Any]:
    text = " ".join((text or "").split())[:1000]
    source = (source or "manual").strip()[:40] or "manual"
    if not text:
        raise ValueError("记忆内容不能为空。")
    memory_id = _new_id("mem")
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        conn.execute(
            """
            INSERT INTO product_memories(id, text, source, enabled, created_at, updated_at, metadata)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (
                memory_id,
                text,
                source,
                now,
                now,
                _json_dumps(
                    {
                        "source": source,
                        "memory_scope": "local_record",
                        "scope_label": "本地记录",
                        "agent_memory_synced": False,
                    }
                ),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_memories WHERE id = ?", (memory_id,)).fetchone()
        assert row is not None
        return _memory_from_row(row)


def update_memory(memory_id: str, *, enabled: bool | None = None, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM product_memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            return None
        next_enabled = bool(row["enabled"]) if enabled is None else bool(enabled)
        conn.execute(
            "UPDATE product_memories SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if next_enabled else 0, now, memory_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_memories WHERE id = ?", (memory_id,)).fetchone()
        assert row is not None
        return _memory_from_row(row)


def delete_memory(memory_id: str, paths: RuntimePaths | None = None) -> bool:
    with conversations._DB_LOCK, _connect(paths) as conn:
        cursor = conn.execute("DELETE FROM product_memories WHERE id = ?", (memory_id,))
        conn.commit()
        return cursor.rowcount > 0


def _capability_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "label": str(row["label"]),
        "description": str(row["description"]),
        "enabled": bool(row["enabled"]),
        "requires_approval": bool(row["requires_approval"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": _json_loads(row["metadata"]),
    }


def list_capabilities(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    with conversations._DB_LOCK, _connect(paths) as conn:
        rows = conn.execute("SELECT * FROM product_capabilities ORDER BY id ASC").fetchall()
    return [_capability_from_row(row) for row in rows]


def update_capability(capability_id: str, *, enabled: bool, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        row = conn.execute("SELECT * FROM product_capabilities WHERE id = ?", (capability_id,)).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE product_capabilities SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now, capability_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_capabilities WHERE id = ?", (capability_id,)).fetchone()
        assert row is not None
        return _capability_from_row(row)


def _profile_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "instructions": str(row["instructions"]),
        "enabled": bool(row["enabled"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": _json_loads(row["metadata"]),
    }


def list_profiles(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    with conversations._DB_LOCK, _connect(paths) as conn:
        rows = conn.execute(
            "SELECT * FROM product_profiles ORDER BY enabled DESC, updated_at DESC, name ASC"
        ).fetchall()
    return [_profile_from_row(row) for row in rows]


def create_profile(
    *,
    name: str,
    instructions: str,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    name = " ".join((name or "").split())[:60]
    instructions = " ".join((instructions or "").split())[:1200]
    if not name:
        raise ValueError("风格名称不能为空。")
    if not instructions:
        raise ValueError("风格说明不能为空。")
    profile_id = _new_id("profile")
    now = _now_iso()
    with conversations._DB_LOCK, _connect(paths) as conn:
        conn.execute(
            """
            INSERT INTO product_profiles(id, name, instructions, enabled, created_at, updated_at, metadata)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (
                profile_id,
                name,
                instructions,
                now,
                now,
                _json_dumps({"source": "desktop", "prompt_injection": False}),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM product_profiles WHERE id = ?", (profile_id,)).fetchone()
        assert row is not None
        return _profile_from_row(row)


def delete_profile(profile_id: str, paths: RuntimePaths | None = None) -> bool:
    with conversations._DB_LOCK, _connect(paths) as conn:
        cursor = conn.execute("DELETE FROM product_profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0


def usage_summary(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    with conversations._DB_LOCK, _connect(runtime_paths) as conn:
        conversation_counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN kind = 'weixin' THEN 1 ELSE 0 END) AS weixin,
                SUM(CASE WHEN kind != 'weixin' THEN 1 ELSE 0 END) AS desktop
            FROM conversations
            """
        ).fetchone()
        message_counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS user,
                SUM(CASE WHEN role = 'assistant' THEN 1 ELSE 0 END) AS assistant,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
                SUM(CASE WHEN status = 'generating' THEN 1 ELSE 0 END) AS running
            FROM messages
            """
        ).fetchone()
        attachment_count = conn.execute("SELECT COUNT(*) AS total FROM attachments").fetchone()
    tasks = list_tasks(runtime_paths)
    memories = list_memories(runtime_paths)
    capabilities = list_capabilities(runtime_paths)
    return {
        "generated_at": _now_iso(),
        "conversations": {
            "total": int(conversation_counts["total"] or 0),
            "desktop": int(conversation_counts["desktop"] or 0),
            "weixin": int(conversation_counts["weixin"] or 0),
        },
        "messages": {
            "total": int(message_counts["total"] or 0),
            "user": int(message_counts["user"] or 0),
            "assistant": int(message_counts["assistant"] or 0),
            "errors": int(message_counts["errors"] or 0),
            "running": int(message_counts["running"] or 0),
        },
        "attachments": {"total": int(attachment_count["total"] or 0)},
        "tasks": {
            "total": len(tasks),
            "active": len([item for item in tasks if item["status"] == "active"]),
            "paused": len([item for item in tasks if item["status"] == "paused"]),
            "completed": len([item for item in tasks if item["status"] == "completed"]),
        },
        "memories": {
            "total": len(memories),
            "active": len([item for item in memories if item["enabled"]]),
        },
        "capabilities": {
            "total": len(capabilities),
            "enabled": len([item for item in capabilities if item["enabled"]]),
        },
        "costs": {
            "available": False,
            "message": "当前没有可靠 token/成本来源，因此不显示费用账单。",
        },
    }


def ui_overview(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    summary = diagnostics_summary(runtime_paths)
    usage = usage_summary(runtime_paths)
    tasks = list_tasks(runtime_paths)
    active_tasks = [item for item in tasks if item["status"] == "active"]
    return {
        "generated_at": _now_iso(),
        "status": "ok" if summary.get("ok") else "needs_attention",
        "diagnostics": summary,
        "usage": usage,
        "tasks": {
            "total": len(tasks),
            "active": len(active_tasks),
            "next": active_tasks[0] if active_tasks else None,
        },
        "model": summary["model"],
        "weixin": summary["weixin"],
    }


def advanced_extensions(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    capabilities = list_capabilities(runtime_paths)
    upstream = upstream_status()
    repo = _repo_root()

    def count_dirs(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"available": False, "count": 0, "items": []}
        items = sorted(item.name for item in path.iterdir() if item.is_dir())[:20]
        return {"available": True, "count": len(items), "items": items}

    return {
        "generated_at": _now_iso(),
        "mode": "guarded",
        "message": "高级扩展支持脱敏导出、安全导入和能力开关；插件安装、raw env 编辑和终端工具默认不开放。",
        "skills": count_dirs(repo / "skills"),
        "plugins": count_dirs(repo / "plugins"),
        "toolsets": [
            {
                "id": item["id"],
                "label": item["label"],
                "enabled": item["enabled"],
                "requires_approval": item["requires_approval"],
            }
            for item in capabilities
        ],
        "upstream": upstream,
        "safe_actions": {
            "config_export": True,
            "product_config_import": True,
            "toolset_toggle": True,
            "plugin_install": False,
            "raw_env_edit": False,
            "terminal_tools": False,
        },
        "dangerous_actions_enabled": False,
    }


SENSITIVE_CONFIG_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "secret",
    "token",
    "password",
    "credential",
    "cookie",
    "authorization",
)


def _redact_sensitive_config(value: Any, *, key: str = "") -> Any:
    lowered_key = key.lower()
    if any(part in lowered_key for part in SENSITIVE_CONFIG_KEY_PARTS):
        if value in {"", None, False}:
            return ""
        return "[已脱敏]"
    if isinstance(value, dict):
        return {str(item_key): _redact_sensitive_config(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact_sensitive_config(item) for item in value]
    return value


def advanced_config_export(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    capabilities = list_capabilities(runtime_paths)
    tasks = list_tasks(runtime_paths)
    profiles = list_profiles(runtime_paths)
    return {
        "version": 1,
        "generated_at": _now_iso(),
        "redacted": True,
        "message": "这是脱敏导出，只包含产品层可安全导入的设置和 Hermes 配置摘要。",
        "sections": {
            "product_capabilities": [
                {"id": item["id"], "enabled": item["enabled"]}
                for item in capabilities
            ],
            "product_tasks": [
                {
                    "title": item["title"],
                    "prompt": item["prompt"],
                    "due_at": item["due_at"],
                    "kind": item["kind"],
                    "schedule": item.get("schedule") or item.get("metadata", {}).get("schedule") or "once",
                    "enabled": item["enabled"],
                }
                for item in tasks
            ],
            "product_profiles": [
                {
                    "name": item["name"],
                    "instructions": item["instructions"],
                    "enabled": item["enabled"],
                }
                for item in profiles
            ],
            "hermes_config_redacted": _redact_sensitive_config(read_hermes_config(runtime_paths)),
        },
        "not_included": [
            "API Key 或 runtime token",
            "微信凭据",
            "聊天正文和附件原文",
            "raw env 编辑能力",
            "插件安装或终端执行能力",
        ],
    }


def _config_sections(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections")
    return sections if isinstance(sections, dict) else payload


def advanced_config_import(payload: dict[str, Any], paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    sections = _config_sections(payload)
    applied = {"capabilities": 0, "tasks": 0, "profiles": 0}
    skipped: list[str] = []

    capabilities = sections.get("product_capabilities")
    if isinstance(capabilities, list):
        for item in capabilities:
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("id") or "").strip()
            enabled = item.get("enabled")
            if capability_id and isinstance(enabled, bool) and update_capability(capability_id, enabled=enabled, paths=runtime_paths):
                applied["capabilities"] += 1

    existing_profiles = {
        (item["name"], item["instructions"])
        for item in list_profiles(runtime_paths)
    }
    profiles = sections.get("product_profiles")
    if isinstance(profiles, list):
        for item in profiles:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            instructions = str(item.get("instructions") or "")
            if (name, instructions) in existing_profiles:
                skipped.append(f"Profile 已存在：{name}")
                continue
            try:
                profile = create_profile(name=name, instructions=instructions, paths=runtime_paths)
            except ValueError as exc:
                skipped.append(str(exc))
                continue
            existing_profiles.add((profile["name"], profile["instructions"]))
            applied["profiles"] += 1

    existing_tasks = {
        (item["title"], item["prompt"], item["due_at"], item.get("schedule") or item.get("metadata", {}).get("schedule") or "once")
        for item in list_tasks(runtime_paths)
    }
    tasks = sections.get("product_tasks")
    if isinstance(tasks, list):
        for item in tasks:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            prompt = str(item.get("prompt") or "")
            due_at = str(item.get("due_at") or "")
            schedule = str(item.get("schedule") or "once")
            kind = str(item.get("kind") or "reminder")
            key = (title, prompt, due_at, schedule)
            if key in existing_tasks:
                skipped.append(f"任务已存在：{title}")
                continue
            try:
                task = create_task(title=title, prompt=prompt, due_at=due_at, kind=kind, schedule=schedule, paths=runtime_paths)
            except ValueError as exc:
                skipped.append(str(exc))
                continue
            if item.get("enabled") is False:
                update_task(task["id"], enabled=False, paths=runtime_paths)
            existing_tasks.add((task["title"], task["prompt"], task["due_at"], task.get("schedule") or "once"))
            applied["tasks"] += 1

    conversations.append_event(
        "advanced.config_imported",
        {"applied": applied, "skipped_count": len(skipped)},
        paths=runtime_paths,
    )
    return {
        "ok": True,
        "message": "安全导入已完成；密钥、raw env、插件安装和终端能力没有导入。",
        "applied": applied,
        "skipped": skipped[:20],
    }


def undo_last_turn(conversation_id: str, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    conversation_id = (conversation_id or "").strip() or conversations.PERSONAL_CONVERSATION_ID
    with conversations._DB_LOCK, _connect(paths) as conn:
        if conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone() is None:
            return None
        rows = conn.execute(
            """
            SELECT rowid, id, role, source FROM messages
            WHERE conversation_id = ?
            ORDER BY rowid DESC
            LIMIT 8
            """,
            (conversation_id,),
        ).fetchall()
        target_ids: list[str] = []
        for index, row in enumerate(rows):
            role = str(row["role"])
            if role == "system":
                continue
            target_ids.append(str(row["id"]))
            if role == "assistant" and index + 1 < len(rows) and str(rows[index + 1]["role"]) == "user":
                target_ids.append(str(rows[index + 1]["id"]))
            break
        if not target_ids:
            return {"ok": False, "message": "这个对话还没有可撤销的消息。", "removed_message_ids": []}
        conn.executemany("DELETE FROM messages WHERE id = ?", [(message_id,) for message_id in target_ids])
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now_iso(), conversation_id))
        conn.commit()
    conversations.append_event(
        "conversation.turn_undone",
        {"conversation_id": conversation_id, "removed_message_ids": target_ids},
        paths=paths,
    )
    return {"ok": True, "message": "已撤销上一轮。", "removed_message_ids": target_ids}


def branch_conversation(
    conversation_id: str,
    *,
    title: str | None = None,
    message_id: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    source = conversations.get_conversation(conversation_id, paths)
    if source is None:
        return None
    branch_title = " ".join((title or f"{source['title']} 分支").split())[:80]
    metadata = {
        "branch_from": source["id"],
        "branch_message_id": message_id or "",
        "copied_attachments": True,
    }
    branch = conversations.create_conversation(title=branch_title, kind="desktop", metadata=metadata, paths=paths)
    source_messages = conversations.list_messages(conversation_id, limit=conversations.MAX_MESSAGE_LIMIT, paths=paths)
    copied = 0
    copied_attachments = 0
    for message in source_messages:
        copied_message = conversations.create_message(
            conversation_id=branch["id"],
            source=str(message.get("source") or "desktop"),
            role=str(message.get("role") or "user"),
            text=str(message.get("text") or ""),
            status=str(message.get("status") or "sent"),
            metadata={
                **(message.get("metadata") if isinstance(message.get("metadata"), dict) else {}),
                "copied_from_message_id": message.get("id"),
            },
            emit_event=False,
            paths=paths,
        )
        for attachment in message.get("attachments") or []:
            attachment_id = str(attachment.get("id") or "")
            if not attachment_id:
                continue
            original = conversations.get_attachment(attachment_id, include_safe_path=True, paths=paths)
            if original is None:
                continue
            try:
                safe_path = is_safe_stored_attachment(str(original.get("safe_path") or ""), paths=paths)
            except AttachmentError:
                continue
            original_metadata = original.get("metadata") if isinstance(original.get("metadata"), dict) else {}
            conversations.create_attachment_record(
                message_id=copied_message["id"],
                conversation_id=branch["id"],
                safe_path=safe_path,
                file_name=str(original.get("file_name") or "attachment"),
                mime_type=str(original.get("mime_type") or "application/octet-stream"),
                size_bytes=int(original.get("size_bytes") or 0),
                summary_status=str(original.get("summary_status") or "ready"),
                summary_text=str(original.get("summary_text") or ""),
                preview_data_url=str(original.get("preview_data_url") or ""),
                reason_cn=str(original.get("reason_cn") or ""),
                metadata={
                    **original_metadata,
                    "copied_from_attachment_id": attachment_id,
                    "copied_from_message_id": message.get("id"),
                    "copied_from_conversation_id": conversation_id,
                },
                paths=paths,
            )
            copied_attachments += 1
        copied += 1
        if message_id and message.get("id") == message_id:
            break
    conversations.append_event(
        "conversation.branched",
        {
            "conversation_id": conversation_id,
            "branch": branch,
            "copied_messages": copied,
            "copied_attachments": copied_attachments,
        },
        paths=paths,
    )
    return {"conversation": branch, "copied_messages": copied, "copied_attachments": copied_attachments}


def save_conversation_summary(conversation_id: str, paths: RuntimePaths | None = None) -> dict[str, Any] | None:
    conversation = conversations.get_conversation(conversation_id, paths)
    if conversation is None:
        return None
    messages = conversations.list_messages(conversation_id, limit=16, paths=paths)
    lines: list[str] = []
    for message in messages[-12:]:
        role = "用户" if message.get("role") == "user" else "小黑子" if message.get("role") == "assistant" else "系统"
        text = " ".join(str(message.get("text") or "").split())
        if not text:
            continue
        lines.append(f"{role}: {text[:160]}")
    if not lines:
        raise ValueError("这个对话还没有可保存的内容。")
    summary_text = f"对话摘要（{conversation['title']}）：\n" + "\n".join(lines)
    memory = create_memory(text=summary_text, source="conversation_summary", paths=paths)
    conversations.append_event(
        "conversation.summary_saved",
        {"conversation_id": conversation_id, "memory_id": memory["id"]},
        paths=paths,
    )
    return {"memory": memory, "message": "已把最近对话保存为本地记录。"}


def model_capabilities(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    runtime_model = current_runtime_model(runtime_paths)
    provider_id = str(runtime_model.get("provider") or "")
    model = str(runtime_model.get("model") or "")
    provider = provider_by_id(provider_id) if provider_id else None
    config = read_hermes_config(runtime_paths)
    image_status = image_recognition_status(provider_id, model, config=config, paths=runtime_paths)
    graph = build_capability_graph(runtime_paths)
    image_node = graph_node(graph, "image.read") or {}
    image_details = image_node.get("details") if isinstance(image_node.get("details"), dict) else {}
    image_capability_status = str(image_node.get("status") or "unknown")
    supports_image = bool(runtime_model.get("configured") and image_capability_status in {"ready", "degraded"})
    supports_files = bool(runtime_model.get("configured"))
    supports_weixin = True
    limitations: list[str] = []
    if not runtime_model.get("configured"):
        limitations.append("还没有设置 AI 服务。")
    if runtime_model.get("configured") and not supports_image:
        limitations.append(str(image_node.get("user_message_cn") or "当前模型和辅助视觉都没有确认支持图片识别，图片只能预览和作为文件保存。"))
    if runtime_model.get("configured") and image_capability_status == "degraded":
        limitations.append(str(image_node.get("user_message_cn") or "图片识别依赖辅助视觉模型，主聊天模型不会直接接收图片。"))
    return {
        "configured": bool(runtime_model.get("configured")),
        "provider": provider_id,
        "provider_name": str(provider.get("display_name") or provider_id) if provider else provider_id,
        "model": model,
        "supports_image": supports_image,
        "main_supports_image": bool(runtime_model.get("configured") and image_details.get("main_supports_image", image_status["main_supports_image"])),
        "auxiliary_configured": bool(image_details.get("auxiliary_configured", image_status["auxiliary_configured"])),
        "image_backend": str(image_details.get("backend") or image_status["backend"]),
        "image_input_mode": str(image_details.get("image_input_mode") or image_status["image_input_mode"]),
        "image_capability_status": image_capability_status,
        "capability_graph": graph,
        "supports_files": supports_files,
        "supports_weixin": supports_weixin,
        "supports_reminders": True,
        "source": "Hermes model metadata + lilsunspot provider config",
        "limitations": limitations,
    }


def _snippet(text: str, query: str, *, max_length: int = 120) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    index = text.lower().find(query.lower())
    if index < 0:
        return text[:max_length]
    start = max(0, index - 36)
    end = min(len(text), index + len(query) + 72)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"[: max_length + 6]


def _conversation_archived(metadata_raw: str) -> bool:
    metadata = _json_loads(metadata_raw)
    return bool(metadata.get("archived_at"))


def search_conversations(
    query: str,
    *,
    include_archived: bool = False,
    limit: int = 20,
    paths: RuntimePaths | None = None,
) -> list[dict[str, Any]]:
    query = " ".join((query or "").split())
    if not query:
        return []
    limit = max(1, min(int(limit or 20), 50))
    pattern = f"%{query}%"
    results: list[dict[str, Any]] = []
    with conversations._DB_LOCK, _connect(paths) as conn:
        message_rows = conn.execute(
            """
            SELECT
                m.id AS message_id,
                m.conversation_id,
                m.text,
                m.created_at,
                m.role,
                m.source,
                c.title AS conversation_title,
                c.kind AS conversation_kind,
                c.metadata AS conversation_metadata
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.text LIKE ?
            ORDER BY m.rowid DESC
            LIMIT ?
            """,
            (pattern, limit),
        ).fetchall()
        attachment_rows = conn.execute(
            """
            SELECT
                a.id AS attachment_id,
                a.message_id,
                a.conversation_id,
                a.file_name,
                a.summary_text,
                a.reason_cn,
                a.created_at,
                c.title AS conversation_title,
                c.kind AS conversation_kind,
                c.metadata AS conversation_metadata
            FROM attachments a
            JOIN conversations c ON c.id = a.conversation_id
            WHERE a.file_name LIKE ? OR a.summary_text LIKE ? OR a.reason_cn LIKE ?
            ORDER BY a.rowid DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()

    for row in message_rows:
        if not include_archived and _conversation_archived(str(row["conversation_metadata"])):
            continue
        results.append(
            {
                "type": "message",
                "conversation_id": str(row["conversation_id"]),
                "conversation_title": str(row["conversation_title"]),
                "conversation_kind": str(row["conversation_kind"]),
                "message_id": str(row["message_id"]),
                "attachment_id": "",
                "source": str(row["source"]),
                "role": str(row["role"]),
                "snippet": _snippet(str(row["text"]), query),
                "created_at": str(row["created_at"]),
            }
        )
    for row in attachment_rows:
        if len(results) >= limit:
            break
        if not include_archived and _conversation_archived(str(row["conversation_metadata"])):
            continue
        summary = str(row["summary_text"] or row["reason_cn"] or row["file_name"])
        results.append(
            {
                "type": "attachment",
                "conversation_id": str(row["conversation_id"]),
                "conversation_title": str(row["conversation_title"]),
                "conversation_kind": str(row["conversation_kind"]),
                "message_id": str(row["message_id"]),
                "attachment_id": str(row["attachment_id"]),
                "source": "attachment",
                "role": "file",
                "snippet": _snippet(summary, query),
                "created_at": str(row["created_at"]),
            }
        )
    return results[:limit]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _changed_files_from_report(text: str) -> int | None:
    total = 0
    found_category_count = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 2 or cells[0] == "Category" or cells[0].startswith("---"):
            continue
        count_raw = cells[1].replace(",", "")
        if not count_raw.isdigit():
            continue
        total += int(count_raw)
        found_category_count = True
    return total if found_category_count else None


def _list_value_after(text: str, prefix: str) -> list[str]:
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        raw = line[len(prefix) :].strip()
        if not raw or raw.lower() == "none":
            return []
        return [item.strip().strip("`") for item in raw.split(",") if item.strip().strip("`")]
    return []


def _empty_upstream_status(summary: str, audit: dict[str, Any] | None = None) -> dict[str, Any]:
    capability_audit = audit or {}
    return {
        "available": bool(capability_audit.get("available")),
        "latest_report": "",
        "generated_at": "",
        "summary": summary,
        "commits_since_base": None,
        "changed_files": None,
        "working_tree_dirty": capability_audit.get("working_tree_dirty"),
        "latest_upstream": str(capability_audit.get("latest_commit") or ""),
        "recorded_base": str(capability_audit.get("recorded_base") or ""),
        "missing_toolsets": list(capability_audit.get("missing_toolsets") or []),
        "missing_configurable_toolsets": list(capability_audit.get("missing_configurable_toolsets") or []),
        "missing_default_config_keys": list(capability_audit.get("missing_default_config_keys") or []),
        "missing_capability_mappings": list(capability_audit.get("missing_capability_mappings") or []),
        "missing_config_mappings": list(capability_audit.get("missing_config_mappings") or []),
        "sync_eligible": bool(capability_audit.get("sync_eligible")),
        "capability_audit": capability_audit,
    }


def upstream_status() -> dict[str, Any]:
    capability_audit = safe_upstream_capability_audit(_repo_root())
    reports_dir = _repo_root() / "lilsunspot" / "notes" / "upstream-sync-reports"
    if not reports_dir.exists():
        return _empty_upstream_status("还没有生成 Hermes upstream 检查报告。", capability_audit)
    reports = sorted(reports_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not reports:
        return _empty_upstream_status("还没有生成 Hermes upstream 检查报告。", capability_audit)
    latest = reports[0]
    text = latest.read_text(encoding="utf-8", errors="replace")

    def value_after(prefix: str) -> str:
        for line in text.splitlines():
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return ""

    commits_raw = value_after("- Upstream commits since comparison base:")
    changed_count = _changed_files_from_report(text)
    dirty_raw = value_after("- Working tree dirty:")
    commits = int(commits_raw) if commits_raw.isdigit() else None
    dirty = dirty_raw == "True" if dirty_raw else None
    summary = "已生成只读检查报告。"
    if commits is not None:
        summary = f"本地缓存 upstream 相对记录 base 有 {commits} 个提交待审计。"
    report_latest = value_after("- Remote commit:")
    report_recorded = value_after("- Recorded base:")
    report_missing_toolsets = _list_value_after(text, "- Missing TOOLSETS in current worktree:")
    report_missing_configurable = _list_value_after(text, "- Missing CONFIGURABLE_TOOLSETS in current worktree:")
    report_missing_default_config = _list_value_after(text, "- Missing DEFAULT_CONFIG keys in current worktree:")
    missing_toolsets = list(capability_audit.get("missing_toolsets") or report_missing_toolsets)
    missing_configurable = list(capability_audit.get("missing_configurable_toolsets") or report_missing_configurable)
    missing_default_config = list(capability_audit.get("missing_default_config_keys") or report_missing_default_config)
    return {
        "available": True,
        "latest_report": str(latest),
        "generated_at": value_after("Generated:"),
        "summary": summary,
        "commits_since_base": commits,
        "changed_files": changed_count,
        "working_tree_dirty": dirty,
        "latest_upstream": str(capability_audit.get("latest_commit") or report_latest),
        "recorded_base": str(capability_audit.get("recorded_base") or report_recorded),
        "missing_toolsets": missing_toolsets,
        "missing_configurable_toolsets": missing_configurable,
        "missing_default_config_keys": missing_default_config,
        "missing_capability_mappings": list(capability_audit.get("missing_capability_mappings") or sorted(set(missing_toolsets) | set(missing_configurable))),
        "missing_config_mappings": list(capability_audit.get("missing_config_mappings") or missing_default_config),
        "sync_eligible": bool(capability_audit.get("sync_eligible")) if capability_audit.get("available") else bool(dirty is False and commits),
        "capability_audit": capability_audit,
    }


def diagnostics_summary(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    runtime_model = current_runtime_model(runtime_paths)
    doctor = run_doctor_checks()
    runtime_descriptor = read_runtime_descriptor(runtime_paths) or {}
    runtime_process = runtime_descriptor.get("process") if isinstance(runtime_descriptor.get("process"), dict) else {}
    weixin = weixin_status()
    reminders = list_reminders(runtime_paths)
    memories = list_memories(runtime_paths)
    capabilities = list_capabilities(runtime_paths)
    active_capabilities = [item for item in capabilities if item["enabled"]]
    weixin_conversations = [
        item for item in conversations.list_conversations(runtime_paths, include_archived=True)
        if item.get("kind") == "weixin" and isinstance(item.get("metadata"), dict)
    ]
    active_weixin = [
        item for item in weixin_conversations
        if item.get("metadata", {}).get("weixin_route_active")
    ]
    return {
        "ok": bool(doctor.get("ok")) and bool(runtime_model.get("configured")),
        "generated_at": _now_iso(),
        "model": model_capabilities(runtime_paths),
        "weixin": {
            "connected": bool(weixin.get("connected")),
            "status": str(weixin.get("status") or ""),
            "message": str(weixin.get("message") or ""),
            "active_conversation_count": len(active_weixin),
        },
        "local_service": {
            "doctor_ok": bool(doctor.get("ok")),
            "runtime_process": runtime_process,
            "process_note": str(runtime_process.get("note_cn") or ""),
            "failed_checks": [
                check for check in doctor.get("checks", [])
                if isinstance(check, dict) and not check.get("ok")
            ],
        },
        "counts": {
            "reminders": len(reminders),
            "active_reminders": len([item for item in reminders if item["enabled"] and not item["completed_at"]]),
            "memories": len(memories),
            "active_memories": len([item for item in memories if item["enabled"]]),
            "capabilities": len(capabilities),
            "enabled_capabilities": len(active_capabilities),
        },
        "upstream": upstream_status(),
    }
