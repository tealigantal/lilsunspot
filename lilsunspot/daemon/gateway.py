from __future__ import annotations

from typing import Any

from .safety import request_safety_approval


WEIXIN_COMMANDS: list[dict[str, Any]] = [
    {
        "name": "/help",
        "enabled": True,
        "description": "显示小黑子微信命令帮助。",
        "approval_required": False,
    },
    {
        "name": "/mode",
        "enabled": True,
        "description": "查看或切换输出模式，例如 /mode pragmatic。",
        "approval_required": False,
    },
    {
        "name": "/approve",
        "enabled": True,
        "description": "批准安全审批请求，例如 /approve approval_xxx。",
        "approval_required": False,
    },
    {
        "name": "/reject",
        "enabled": True,
        "description": "拒绝安全审批请求，例如 /reject approval_xxx。",
        "approval_required": False,
    },
]


def weixin_status() -> dict[str, Any]:
    return {
        "gateway": "weixin",
        "available": False,
        "connected": False,
        "commands_available": True,
        "message": "微信真实连接尚未启用；当前版本不会扫码登录或直接发送消息。",
    }


def weixin_commands() -> dict[str, Any]:
    return {
        "gateway": "weixin",
        "commands": WEIXIN_COMMANDS,
        "message": "这些是产品层命令入口；真实微信收发尚未启用。",
    }


def parse_weixin_command(text: str) -> dict[str, Any]:
    raw_text = text.strip()
    if not raw_text:
        return {
            "ok": False,
            "kind": "empty",
            "message": "微信命令不能为空。",
        }
    if not raw_text.startswith("/"):
        return {
            "ok": False,
            "kind": "chat_message",
            "message": "微信聊天接入尚未实现，当前只能处理命令。",
        }

    command, _, raw_argument = raw_text.partition(" ")
    command = command.lower()
    argument = raw_argument.strip()

    if command == "/help":
        return {
            "ok": True,
            "kind": "help",
            "message": "可用命令：/help、/mode <模式>、/approve <审批编号>、/reject <审批编号>。",
        }
    if command == "/mode":
        if not argument:
            return {
                "ok": True,
                "kind": "list_modes",
                "message": "请使用 /mode <模式> 切换输出风格。",
            }
        return {
            "ok": True,
            "kind": "select_mode",
            "mode": argument.split()[0],
            "message": "准备切换输出风格。",
        }
    if command in {"/approve", "/reject"}:
        if not argument:
            return {
                "ok": False,
                "kind": "approval_decision",
                "message": f"请提供审批编号，例如 {command} approval_xxx。",
            }
        return {
            "ok": True,
            "kind": "approval_decision",
            "approval_id": argument.split()[0],
            "decision": "approved" if command == "/approve" else "rejected",
            "message": "准备处理安全审批。",
        }

    return {
        "ok": False,
        "kind": "unknown_command",
        "message": "没有识别这个微信命令。请发送 /help 查看可用命令。",
    }


def request_weixin_send_approval(recipient: str, message: str) -> dict[str, Any]:
    recipient_value = recipient.strip()
    message_value = message.strip()
    if not recipient_value:
        raise ValueError("微信联系人不能为空。")
    if not message_value:
        raise ValueError("微信消息不能为空。")

    preview = message_value[:80]
    if len(message_value) > 80:
        preview = f"{preview}..."

    approval_result = request_safety_approval(
        "send_weixin_message",
        f"发送微信消息给 {recipient_value}",
        {
            "recipient": recipient_value,
            "message_preview": preview,
            "message_length": len(message_value),
        },
        "weixin",
    )
    return {
        "ok": False,
        "gateway": "weixin",
        "status": "approval_required" if approval_result.get("approval_required") else "unavailable",
        "approval_required": bool(approval_result.get("approval_required")),
        "approval": approval_result.get("approval"),
        "message": "微信发送需要安全审批，当前版本不会直接发送消息。",
    }
