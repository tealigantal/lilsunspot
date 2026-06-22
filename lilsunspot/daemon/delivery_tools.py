from __future__ import annotations

import json
from typing import Any

from .delivery_actions import create_deliverable_file_action, deliver_file_action, return_attachment_action


LILSUNSPOT_DELIVERY_TOOLSET = "lilsunspot_delivery"
RETURN_ATTACHMENT_TOOL = "lilsunspot_return_attachment"
DELIVER_FILE_TOOL = "lilsunspot_deliver_file"
CREATE_DELIVERABLE_FILE_TOOL = "lilsunspot_create_deliverable_file"


RETURN_ATTACHMENT_SCHEMA = {
    "name": RETURN_ATTACHMENT_TOOL,
    "description": (
        "Return one existing safe lilsunspot attachment to the current user. "
        "Use this only when the user asks to get back an attachment already "
        "available in the current conversation and the id starts with att_. "
        "Do not use this for newly generated files. Do not pass a target; "
        "the current desktop or Weixin route is selected by lilsunspot."
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


DELIVER_FILE_SCHEMA = {
    "name": DELIVER_FILE_TOOL,
    "description": (
        "Deliver a newly generated local file to the current lilsunspot user. "
        "The path must be a real file inside the current turn's safe deliverable "
        "directory. Use this after writing the file with the Hermes write_file tool."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path, or relative path under the current safe deliverable directory.",
            },
            "caption": {
                "type": "string",
                "description": "Optional short Chinese caption to send with the file.",
            },
        },
        "required": ["path"],
    },
}


CREATE_DELIVERABLE_FILE_SCHEMA = {
    "name": CREATE_DELIVERABLE_FILE_TOOL,
    "description": (
        "Create one real file in the current lilsunspot safe deliverable directory "
        "and deliver it to the current user. Use content_text for UTF-8 text files "
        "or content_base64 for binary files. Do not include both. For ordinary tables "
        "use .csv by default; use .xlsx only when the user explicitly asks for Excel."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Safe display file name, for example report.md, summary.txt, data.csv, data.xlsx, or chart.png.",
            },
            "content_text": {
                "type": "string",
                "description": (
                    "UTF-8 text content. Use this for markdown, txt, csv, json, html, etc. "
                    "If file_name ends with .xlsx or .docx, lilsunspot converts this text into a real Office file. "
                    "Do not use this for PDF."
                ),
            },
            "content_base64": {
                "type": "string",
                "description": "Base64 bytes for real binary files such as png or pdf. Do not include content_text at the same time.",
            },
            "mime_type": {
                "type": "string",
                "description": "Optional MIME type, for example text/markdown or image/png.",
            },
            "caption": {
                "type": "string",
                "description": "Optional short Chinese caption to send with the file.",
            },
        },
        "required": ["file_name"],
    },
}


def return_attachment_handler(args: dict[str, Any], **_kwargs: Any) -> str:
    action = return_attachment_action(
        str((args or {}).get("attachment_id") or ""),
        str((args or {}).get("caption") or ""),
    )
    return json.dumps(action, ensure_ascii=False)


def deliver_file_handler(args: dict[str, Any], **_kwargs: Any) -> str:
    action = deliver_file_action(
        str((args or {}).get("path") or ""),
        str((args or {}).get("caption") or ""),
    )
    return json.dumps(action, ensure_ascii=False)


def create_deliverable_file_handler(args: dict[str, Any], **_kwargs: Any) -> str:
    payload = args or {}
    action = create_deliverable_file_action(
        file_name=str(payload.get("file_name") or ""),
        content_text=payload.get("content_text") if "content_text" in payload else None,
        content_base64=payload.get("content_base64") if "content_base64" in payload else None,
        mime_type=str(payload.get("mime_type") or ""),
        caption=str(payload.get("caption") or ""),
    )
    return json.dumps(action, ensure_ascii=False)


def register_delivery_tools() -> None:
    from tools.registry import registry

    definitions = [
        (
            RETURN_ATTACHMENT_TOOL,
            RETURN_ATTACHMENT_SCHEMA,
            return_attachment_handler,
            "Return an existing lilsunspot attachment to the current conversation.",
        ),
        (
            DELIVER_FILE_TOOL,
            DELIVER_FILE_SCHEMA,
            deliver_file_handler,
            "Deliver a generated file from the safe lilsunspot turn directory.",
        ),
        (
            CREATE_DELIVERABLE_FILE_TOOL,
            CREATE_DELIVERABLE_FILE_SCHEMA,
            create_deliverable_file_handler,
            "Create and deliver a file in the safe lilsunspot turn directory.",
        ),
    ]
    for name, schema, handler, description in definitions:
        if registry.get_entry(name) is not None:
            continue
        registry.register(
            name=name,
            toolset=LILSUNSPOT_DELIVERY_TOOLSET,
            schema=schema,
            handler=handler,
            check_fn=lambda: True,
            description=description,
        )
