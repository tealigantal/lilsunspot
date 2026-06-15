from __future__ import annotations

import json
from typing import Any

from .delivery_actions import return_attachment_action


LILSUNSPOT_DELIVERY_TOOLSET = "lilsunspot_delivery"
RETURN_ATTACHMENT_TOOL = "lilsunspot_return_attachment"


RETURN_ATTACHMENT_SCHEMA = {
    "name": RETURN_ATTACHMENT_TOOL,
    "description": (
        "Return one existing safe lilsunspot attachment to the current user. "
        "Use this only when the user asks to get back an attachment already "
        "available in the current conversation. Do not pass a target; the "
        "current desktop or Weixin route is selected by lilsunspot."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "attachment_id": {
                "type": "string",
                "description": "The attachment_id from the current conversation attachment list.",
            },
            "caption": {
                "type": "string",
                "description": "Optional short Chinese caption to send with the attachment.",
            },
        },
        "required": ["attachment_id"],
    },
}


def return_attachment_handler(args: dict[str, Any], **_kwargs: Any) -> str:
    action = return_attachment_action(
        str((args or {}).get("attachment_id") or ""),
        str((args or {}).get("caption") or ""),
    )
    return json.dumps(action, ensure_ascii=False)


def register_delivery_tools() -> None:
    from tools.registry import registry

    if registry.get_entry(RETURN_ATTACHMENT_TOOL) is not None:
        return

    registry.register(
        name=RETURN_ATTACHMENT_TOOL,
        toolset=LILSUNSPOT_DELIVERY_TOOLSET,
        schema=RETURN_ATTACHMENT_SCHEMA,
        handler=return_attachment_handler,
        check_fn=lambda: True,
        description="Return an existing lilsunspot attachment to the current conversation.",
    )
