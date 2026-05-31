from __future__ import annotations

from typing import Any


def weixin_status() -> dict[str, Any]:
    return {
        "gateway": "weixin",
        "available": False,
        "connected": False,
        "message": "Weixin gateway 还是占位模块，当前版本不会扫码登录或发送消息。",
    }


def weixin_commands() -> dict[str, Any]:
    return {
        "gateway": "weixin",
        "commands": [
            {"name": "/help", "enabled": False, "description": "显示小黑子微信命令帮助。"},
            {"name": "/mode", "enabled": False, "description": "切换输出模式。"},
            {"name": "/approve", "enabled": False, "description": "批准安全审批请求。"},
        ],
    }
