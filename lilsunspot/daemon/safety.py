from __future__ import annotations

from typing import Any

from .providers import SAFETY_POLICY_FILE, load_yaml_resource


def load_safety_policy() -> dict[str, Any]:
    data = load_yaml_resource(SAFETY_POLICY_FILE)
    return data if isinstance(data, dict) else {}


def list_pending_approvals() -> dict[str, Any]:
    return {
        "pending": [],
        "message": "安全审批队列还是占位模块，当前没有待处理请求。",
    }


def describe_approval_placeholder(operation: str) -> dict[str, Any]:
    return {
        "ok": False,
        "operation": operation,
        "message": "安全审批执行能力尚未实现。",
        "suggestion": "后续任务会接入真实审批队列。",
    }
