from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import conversations
from .attachments import AttachmentError, assert_safe_attachment_path, is_safe_stored_attachment, register_message_attachments
from .config_paths import RuntimePaths, ensure_runtime_dirs


ATTACHMENT_MEDIA_PREFIX = "lilsunspot-attachment://"
DELIVERY_EMPTY_TEXT = "文件已放在下面。"

_ATTACHMENT_MEDIA_RE = re.compile(
    r'''[`"']?MEDIA:\s*lilsunspot-attachment://(?P<id>att_[A-Za-z0-9_-]+)[`"',.;:)\]}]*''',
    re.IGNORECASE,
)
_MEDIA_EXTENSIONS = (
    "png",
    "jpe?g",
    "gif",
    "webp",
    "bmp",
    "mp4",
    "mov",
    "avi",
    "mkv",
    "webm",
    "ogg",
    "opus",
    "mp3",
    "wav",
    "m4a",
    "flac",
    "epub",
    "pdf",
    "zip",
    "rar",
    "7z",
    "docx?",
    "xlsx?",
    "pptx?",
    "txt",
    "csv",
)
_WINDOWS_MEDIA_RE = re.compile(
    r'''[`"']?MEDIA:\s*(?P<path>`[^`\n]+`|"[^"\n]+"|'[^'\n]+'|(?:[A-Za-z]:\\|\\\\)[^\n`"']+?\.(?:'''
    + "|".join(_MEDIA_EXTENSIONS)
    + r'''))(?=[\s`"',;:)\]}]|$)[`"']?''',
    re.IGNORECASE,
)
_ANY_MEDIA_RE = re.compile(r'''[`"']?MEDIA:\s*\S+[^\n]*''')


@dataclass
class PreparedDelivery:
    visible_text: str
    outbound_text: str
    media_paths: list[str]
    status: str
    delivered_count: int
    rejected_count: int
    reason_code: str

    def metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "delivered_count": self.delivered_count,
            "rejected_count": self.rejected_count,
            "reason_code": self.reason_code,
        }


def attachment_delivery_prompt(
    attachments: list[dict[str, Any]] | None = None,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    paths: RuntimePaths | None = None,
    limit: int = 8,
) -> str:
    runtime_paths = paths or ensure_runtime_dirs()
    available = _available_attachments(attachments or [], conversation_id=conversation_id, paths=runtime_paths, limit=limit)
    if not available:
        return ""

    lines = [
        "当前聊天已有这些安全附件引用，可按用户要求返还给当前聊天或微信同频道：",
    ]
    for item in available:
        name = str(item.get("file_name") or "附件")
        mime_type = str(item.get("mime_type") or "application/octet-stream")
        status = str(item.get("summary_status") or "unknown")
        marker = f"MEDIA:{ATTACHMENT_MEDIA_PREFIX}{item['id']}"
        summary = _short_attachment_note(item)
        if summary:
            lines.append(f"- {name}；类型：{mime_type}；状态：{status}；摘要：{summary}；返还标记：{marker}")
        else:
            lines.append(f"- {name}；类型：{mime_type}；状态：{status}；返还标记：{marker}")
    lines.append(
        "如果用户说“把这张图/刚才的文件再发给我/返还附件”，请在最终回复中包含对应返还标记；"
        "不要显示本地路径、MEDIA 标记、工具名或微信内部能力名。"
    )
    return "\n".join(lines)


def add_delivery_context_to_prompt(
    prompt: str,
    *,
    attachments: list[dict[str, Any]] | None = None,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    paths: RuntimePaths | None = None,
) -> str:
    context = attachment_delivery_prompt(attachments, conversation_id=conversation_id, paths=paths)
    if not context:
        return prompt
    return f"{prompt.strip()}\n\n{context}".strip()


def prepare_assistant_delivery(
    reply: str,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    paths: RuntimePaths | None = None,
    include_outbound_media: bool = False,
) -> PreparedDelivery:
    runtime_paths = paths or ensure_runtime_dirs()
    raw_reply = str(reply or "")
    attachment_ids, cleaned = _extract_attachment_refs(raw_reply)
    media_paths, cleaned = _extract_local_media(cleaned)
    unsupported_count = 1 if "MEDIA:" in cleaned else 0
    cleaned = _strip_unknown_media(cleaned)

    accepted: list[str] = []
    rejections: list[str] = []
    for attachment_id in attachment_ids:
        resolved, reason = _resolve_attachment_ref(attachment_id, conversation_id=conversation_id, paths=runtime_paths)
        if resolved:
            accepted.append(resolved)
        else:
            rejections.append(reason)
    for media_path in media_paths:
        resolved, reason = _resolve_media_path(media_path, conversation_id=conversation_id, paths=runtime_paths)
        if resolved:
            accepted.append(resolved)
        else:
            rejections.append(reason)
    if unsupported_count:
        rejections.extend(["unsupported_media"] * unsupported_count)

    accepted = _dedupe(accepted)
    visible_text = _clean_visible_text(cleaned)
    delivered_count = len(accepted)
    rejected_count = len(rejections)
    status = _delivery_status(delivered_count, rejected_count)
    reason_code = rejections[0] if rejections else ""
    if not visible_text and delivered_count:
        visible_text = DELIVERY_EMPTY_TEXT
    elif not visible_text and rejected_count:
        visible_text = _reason_message(reason_code)

    outbound_text = visible_text
    if include_outbound_media and accepted:
        media_lines = [f"MEDIA:{path}" for path in accepted]
        outbound_text = "\n".join([part for part in [visible_text, *media_lines] if part]).strip()

    return PreparedDelivery(
        visible_text=visible_text,
        outbound_text=outbound_text,
        media_paths=accepted,
        status=status,
        delivered_count=delivered_count,
        rejected_count=rejected_count,
        reason_code=reason_code,
    )


def register_prepared_delivery(
    prepared: PreparedDelivery,
    *,
    message_id: str,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    source: str = "assistant_delivery",
    paths: RuntimePaths | None = None,
) -> list[dict[str, Any]]:
    if not prepared.media_paths:
        return []
    return register_message_attachments(
        message_id=message_id,
        conversation_id=conversation_id,
        media_urls=prepared.media_paths,
        media_types=[],
        source=source,
        paths=paths,
    )


def _available_attachments(
    current_attachments: list[dict[str, Any]],
    *,
    conversation_id: str,
    paths: RuntimePaths,
    limit: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for attachment in current_attachments:
        if str(attachment.get("conversation_id") or conversation_id) != conversation_id:
            continue
        attachment_id = str(attachment.get("id") or "").strip()
        if not attachment_id or attachment_id in seen:
            continue
        seen.add(attachment_id)
        items.append(attachment)
    for attachment in conversations.list_recent_attachments(
        conversation_id=conversation_id,
        limit=limit,
        include_safe_path=False,
        paths=paths,
    ):
        attachment_id = str(attachment.get("id") or "").strip()
        if not attachment_id or attachment_id in seen:
            continue
        seen.add(attachment_id)
        items.append(attachment)
        if len(items) >= limit:
            break
    return items[:limit]


def _short_attachment_note(attachment: dict[str, Any]) -> str:
    summary = str(attachment.get("summary_text") or "").strip()
    reason = str(attachment.get("reason_cn") or "").strip()
    text = summary or reason
    text = " ".join(text.split())
    if len(text) > 160:
        text = f"{text[:160].rstrip()}..."
    return text


def _extract_attachment_refs(text: str) -> tuple[list[str], str]:
    refs: list[str] = []

    def replace(match: re.Match[str]) -> str:
        refs.append(match.group("id"))
        return ""

    return refs, _ATTACHMENT_MEDIA_RE.sub(replace, text)


def _extract_local_media(text: str) -> tuple[list[str], str]:
    paths: list[str] = []
    cleaned = text
    try:
        from gateway.platforms.base import BasePlatformAdapter

        media_files, cleaned = BasePlatformAdapter.extract_media(cleaned)
        paths.extend(str(path) for path, _is_voice in media_files)
    except Exception:
        pass
    windows_paths: list[str] = []

    def replace_windows(match: re.Match[str]) -> str:
        value = _strip_path_wrapper(match.group("path"))
        if value:
            windows_paths.append(value)
        return ""

    cleaned = _WINDOWS_MEDIA_RE.sub(replace_windows, cleaned)
    paths.extend(windows_paths)
    return paths, cleaned


def _strip_unknown_media(text: str) -> str:
    if "MEDIA:" not in text:
        return text
    return _ANY_MEDIA_RE.sub("", text)


def _strip_path_wrapper(path: str) -> str:
    value = path.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`\"'":
        value = value[1:-1].strip()
    return value.lstrip("`\"'").rstrip("`\"',.;:)}]")


def _resolve_attachment_ref(
    attachment_id: str,
    *,
    conversation_id: str,
    paths: RuntimePaths,
) -> tuple[str | None, str]:
    attachment = conversations.get_attachment(attachment_id, include_safe_path=True, paths=paths)
    if not attachment:
        return None, "missing_attachment"
    if str(attachment.get("conversation_id") or "") != conversation_id:
        return None, "cross_conversation"
    try:
        resolved = is_safe_stored_attachment(str(attachment.get("safe_path") or ""), paths)
    except AttachmentError:
        return None, "unsafe_path"
    return str(resolved), ""


def _resolve_media_path(
    media_path: str,
    *,
    conversation_id: str,
    paths: RuntimePaths,
) -> tuple[str | None, str]:
    try:
        resolved = assert_safe_attachment_path(media_path, paths)
    except AttachmentError:
        return None, "unsafe_path"
    stored_attachment = _stored_attachment_for_path(resolved, paths)
    if stored_attachment is not None and str(stored_attachment.get("conversation_id") or "") != conversation_id:
        return None, "cross_conversation"
    if _looks_like_stored_attachment_path(resolved, paths) and stored_attachment is None:
        return None, "missing_attachment"
    return str(resolved), ""


def _stored_attachment_for_path(path: Path, paths: RuntimePaths) -> dict[str, Any] | None:
    return conversations.find_attachment_by_safe_path(path, include_safe_path=True, paths=paths)


def _looks_like_stored_attachment_path(path: Path, paths: RuntimePaths) -> bool:
    try:
        is_safe_stored_attachment(path, paths)
        return True
    except AttachmentError:
        return False


def _dedupe(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        key = str(Path(path).resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _clean_visible_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("[[audio_as_voice]]", "").replace("[[as_document]]", "").splitlines()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _delivery_status(delivered_count: int, rejected_count: int) -> str:
    if delivered_count and rejected_count:
        return "partial"
    if delivered_count:
        return "delivered"
    if rejected_count:
        return "rejected"
    return "none"


def _reason_message(reason_code: str) -> str:
    return {
        "unsafe_path": "这个文件不在小黑子的安全附件目录里，不能直接返还。",
        "missing_attachment": "没有找到要返还的附件。",
        "cross_conversation": "这个附件属于另一个对话，不能在当前对话里返还。",
        "adapter_unavailable": "当前发送通道不可用。",
        "unsupported_media": "这个媒体标记暂时不能作为附件返还。",
    }.get(reason_code, "附件暂时不能返还。")
