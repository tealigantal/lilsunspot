from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import conversations
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
        "description": "允许保存本地提醒；自动执行器后续单独接入。",
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


def _memory_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "text": str(row["text"]),
        "source": str(row["source"]),
        "enabled": bool(row["enabled"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "metadata": _json_loads(row["metadata"]),
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
            (memory_id, text, source, now, now, _json_dumps({"source": source})),
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
