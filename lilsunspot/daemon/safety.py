from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_paths import ensure_runtime_dirs
from .providers import SAFETY_POLICY_FILE, load_yaml_resource


APPROVALS_FILE_NAME = "safety-approvals.json"
VALID_DECISIONS = {"approved", "rejected"}
SENSITIVE_DETAIL_KEYS = {"api_key", "apikey", "authorization", "secret", "token", "runtime_token"}


class ApprovalNotFoundError(ValueError):
    pass


def load_safety_policy() -> dict[str, Any]:
    data = load_yaml_resource(SAFETY_POLICY_FILE)
    return data if isinstance(data, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _approvals_file() -> Path:
    return ensure_runtime_dirs().data_dir / APPROVALS_FILE_NAME


def _redact_runtime_token_text(value: str) -> str:
    try:
        from .auth import load_or_create_token

        runtime_token = load_or_create_token()
    except Exception:
        runtime_token = ""
    if runtime_token:
        return value.replace(runtime_token, "[已隐藏]")
    return value


def _empty_store() -> dict[str, list[dict[str, Any]]]:
    return {"approvals": []}


def _read_store() -> dict[str, list[dict[str, Any]]]:
    path = _approvals_file()
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    approvals = data.get("approvals") if isinstance(data, dict) else None
    if not isinstance(approvals, list):
        return _empty_store()
    return {"approvals": [item for item in approvals if isinstance(item, dict)]}


def _write_store(store: dict[str, list[dict[str, Any]]]) -> None:
    path = _approvals_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _new_approval_id(existing: list[dict[str, Any]]) -> str:
    existing_ids = {str(item.get("id") or "") for item in existing}
    for _ in range(10):
        approval_id = f"approval_{secrets.token_hex(8)}"
        if approval_id not in existing_ids:
            return approval_id
    raise RuntimeError("无法创建安全审批编号。")


def _redact_detail_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_DETAIL_KEYS:
                redacted[key_text] = "[已隐藏]"
            else:
                redacted[key_text] = _redact_detail_value(child)
        return redacted
    if isinstance(value, list):
        return [_redact_detail_value(item) for item in value]
    if isinstance(value, str):
        return _redact_runtime_token_text(value)
    return value


def _public_approval(approval: dict[str, Any]) -> dict[str, Any]:
    public = dict(approval)
    details = public.get("details")
    public["details"] = _redact_detail_value(details) if isinstance(details, dict) else {}
    return public


def operation_requires_approval(operation: str) -> bool:
    policy = load_safety_policy()
    operation_id = operation.strip()
    high_risk = policy.get("high_risk") if isinstance(policy.get("high_risk"), dict) else {}
    operations = high_risk.get("operations") if isinstance(high_risk.get("operations"), list) else []
    if operation_id in {str(item) for item in operations}:
        return bool(high_risk.get("requires_approval", True))

    defaults = policy.get("defaults") if isinstance(policy.get("defaults"), dict) else {}
    return bool(defaults.get("unknown_operation_requires_approval", True))


def request_safety_approval(
    operation: str,
    summary: str,
    details: dict[str, Any] | None = None,
    source: str = "local_api",
) -> dict[str, Any]:
    operation_id = operation.strip()
    if not operation_id:
        raise ValueError("审批操作不能为空。")

    if not operation_requires_approval(operation_id):
        return {
            "ok": True,
            "approval_required": False,
            "operation": operation_id,
            "message": "这个操作当前不需要安全审批。",
        }

    store = _read_store()
    approval = {
        "id": _new_approval_id(store["approvals"]),
        "operation": operation_id,
        "status": "pending",
        "summary": _redact_runtime_token_text(summary.strip() or f"请求执行 {operation_id}"),
        "source": _redact_runtime_token_text(source.strip() or "local_api"),
        "details": _redact_detail_value(details or {}),
        "created_at": _now_iso(),
        "decided_at": None,
    }
    store["approvals"].append(approval)
    _write_store(store)
    return {
        "ok": True,
        "approval_required": True,
        "approval": _public_approval(approval),
        "message": "已创建安全审批，请在执行前确认。",
    }


def list_pending_approvals() -> dict[str, Any]:
    approvals = [_public_approval(item) for item in _read_store()["approvals"]]
    pending = [item for item in approvals if item.get("status") == "pending"]
    history = [item for item in approvals if item.get("status") != "pending"]
    return {
        "pending": pending,
        "history": history,
        "message": "当前没有待处理请求。" if not pending else f"当前有 {len(pending)} 个待审批请求。",
    }


def decide_approval(approval_id: str, decision: str) -> dict[str, Any]:
    normalized_decision = decision.strip().lower()
    if normalized_decision not in VALID_DECISIONS:
        raise ValueError("审批决定只能是 approved 或 rejected。")

    store = _read_store()
    for approval in store["approvals"]:
        if str(approval.get("id") or "") != approval_id:
            continue
        if approval.get("status") != "pending":
            raise ValueError("这个审批已经处理过。")
        approval["status"] = normalized_decision
        approval["decided_at"] = _now_iso()
        _write_store(store)
        return {
            "ok": True,
            "approval": _public_approval(approval),
            "message": "审批已通过。" if normalized_decision == "approved" else "审批已拒绝。",
        }

    raise ApprovalNotFoundError("没有找到这个审批请求。")


def describe_approval_placeholder(operation: str) -> dict[str, Any]:
    return {
        **request_safety_approval(operation, f"请求执行 {operation}", {}, "placeholder_api"),
        "suggestion": "请在安全页查看并处理审批请求。",
    }
