from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import conversations
from .attachments import assert_safe_attachment_path, is_safe_stored_attachment, register_message_attachments
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .delivery_actions import validate_deliverable_file_for_delivery


ATTACHMENT_MEDIA_PREFIX = "lilsunspot-attachment://"
DELIVERY_EMPTY_TEXT = "文件已放在下面。"

_ATTACHMENT_MEDIA_RE = re.compile(
    r'''[`"']?MEDIA:\s*lilsunspot-attachment://(?P<id>att_[A-Za-z0-9_-]+)[`"',.;:)\]}]*''',
    re.IGNORECASE,
)
_ATTACHMENT_MARKDOWN_RE = re.compile(
    r'''!?\[[^\]\n]{0,240}\]\(\s*<?lilsunspot-attachment://(?P<id>att_[A-Za-z0-9_-]+)>?\s*\)''',
    re.IGNORECASE,
)
_ATTACHMENT_URI_RE = re.compile(
    r'''[`"']?lilsunspot-attachment://(?P<id>att_[A-Za-z0-9_-]+)[`"',.;:)\]}]*''',
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
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
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
    media_items: list[dict[str, str]]
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
            "reason_text": _reason_message(self.reason_code) if self.reason_code else "",
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
        "当前聊天已有这些安全附件。用户要求把已有附件发回当前聊天时，必须调用工具 lilsunspot_return_attachment；"
        "不要在回复正文里写本地路径、URL、MEDIA 标记或 lilsunspot-attachment 内部 URI：",
    ]
    for item in available:
        name = str(item.get("file_name") or "附件")
        mime_type = str(item.get("mime_type") or "application/octet-stream")
        status = str(item.get("summary_status") or "unknown")
        media_kind = "image" if mime_type.lower().startswith("image/") else "document"
        summary = _short_attachment_note(item)
        if summary:
            lines.append(
                f"- attachment_id: {item['id']}；file_name: {name}；media_kind: {media_kind}；"
                f"mime_type: {mime_type}；status: {status}；summary: {summary}"
            )
        else:
            lines.append(
                f"- attachment_id: {item['id']}；file_name: {name}；media_kind: {media_kind}；"
                f"mime_type: {mime_type}；status: {status}"
            )
    lines.append(
        "如果用户说“把这张图/刚才的文件再发给我/返还附件”，请调用 lilsunspot_return_attachment；"
        "最终可见回复只写自然中文，不要显示工具名、路径、URL、MEDIA 标记或内部 URI。"
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


def generated_file_delivery_prompt(deliverable_dir: Path) -> str:
    return "\n".join(
        [
            "用户要求生成新文件、报告、表格、图片文件或把新文件发给当前聊天时，必须创建真实文件并交付。",
            f"本轮唯一允许写入和交付新文件的目录：{deliverable_dir}",
            "优先流程：直接调用 lilsunspot_create_deliverable_file(file_name, content_text?, content_base64?, mime_type?, caption?) 创建并交付单个文件。",
            "普通“表格/清单/数据表”默认生成 .csv；只有用户明确要求 Excel 或 xlsx 时才生成真实 .xlsx。",
            ".xlsx/.docx/.pdf 不能把纯文本换扩展名伪装成文件；需要 Excel/Word 时生成真实 Office 文件，PDF 需要真实 PDF 二进制内容。",
            "兼容流程：如果已经用 Hermes write_file 写入上面目录内的真实文件，再调用 lilsunspot_deliver_file(path, caption?)。",
            "已有附件返还只使用 lilsunspot_return_attachment(att_...)；新生成文件绝不能把任务名、todo id、文件名或 write_work 当作 attachment_id。",
            "最终可见回复只写自然中文；不要在正文里显示本地路径、URL、MEDIA 标记或 lilsunspot-attachment 内部 URI。",
        ]
    )


def prepare_assistant_delivery(
    reply: str,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    paths: RuntimePaths | None = None,
    delivery_actions: list[dict[str, Any]] | None = None,
    include_outbound_media: bool = False,
) -> PreparedDelivery:
    runtime_paths = paths or ensure_runtime_dirs()
    raw_reply = str(reply or "")
    invalid_attachment_refs, cleaned = _extract_invalid_attachment_refs(raw_reply)
    media_paths, cleaned = _extract_local_media(cleaned)
    unsupported_count = 1 if "MEDIA:" in cleaned else 0
    cleaned = _strip_unknown_media(cleaned)

    accepted: list[str] = []
    accepted_items: list[dict[str, str]] = []
    rejections: list[str] = []
    for action in delivery_actions or []:
        resolved, reason = _resolve_delivery_action(action, conversation_id=conversation_id, paths=runtime_paths)
        if resolved:
            accepted.append(resolved)
            accepted_items.append({"path": resolved, "media_kind": _media_kind_from_action(action, resolved)})
        else:
            rejections.append(reason)
    for media_path in media_paths:
        resolved, reason = _resolve_media_path(media_path, conversation_id=conversation_id, paths=runtime_paths)
        if resolved:
            accepted.append(resolved)
            accepted_items.append({"path": resolved, "media_kind": _media_kind_from_path(resolved)})
        else:
            rejections.append(reason)
    if invalid_attachment_refs:
        rejections.extend(["invalid_delivery_output"] * invalid_attachment_refs)
    if unsupported_count:
        rejections.extend(["unsupported_media"] * unsupported_count)

    accepted = _dedupe(accepted)
    accepted_items = _dedupe_media_items(accepted_items)
    visible_text = _clean_visible_text(cleaned)
    delivered_count = len(accepted)
    rejected_count = len(rejections)
    status = _delivery_status(delivered_count, rejected_count)
    reason_code = rejections[0] if rejections else ""
    if rejected_count and not delivered_count:
        reason_text = _reason_message(reason_code)
        visible_text = f"{visible_text}\n\n{reason_text}".strip() if visible_text else reason_text
    elif not visible_text and delivered_count:
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
        media_items=accepted_items,
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


def _extract_invalid_attachment_refs(text: str) -> tuple[int, str]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return ""

    cleaned = _ATTACHMENT_MARKDOWN_RE.sub(replace, text)
    cleaned = _ATTACHMENT_MEDIA_RE.sub(replace, cleaned)
    cleaned = _ATTACHMENT_URI_RE.sub(replace, cleaned)
    return count, cleaned


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


def _resolve_delivery_action(
    action: dict[str, Any],
    *,
    conversation_id: str,
    paths: RuntimePaths,
) -> tuple[str | None, str]:
    if not isinstance(action, dict):
        return None, "invalid_delivery_action"
    if action.get("ok") is False:
        return None, str(action.get("reason_code") or "delivery_action_failed")
    attachment_id = str(action.get("attachment_id") or "").strip()
    if attachment_id:
        return _resolve_attachment_ref(attachment_id, conversation_id=conversation_id, paths=paths)
    safe_path = str(action.get("safe_path") or "").strip()
    if safe_path:
        return _resolve_generated_delivery_path(safe_path, conversation_id=conversation_id, paths=paths)
    return None, "invalid_delivery_action"


def _media_kind_from_action(action: dict[str, Any], path: str) -> str:
    media_kind = str(action.get("media_kind") or "").strip().lower()
    if media_kind == "image":
        return "image"
    if media_kind == "document":
        return "document"
    return _media_kind_from_path(path)


def _media_kind_from_path(path: str) -> str:
    return "image" if Path(path).suffix.lower() in _IMAGE_SUFFIXES else "document"


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
    except Exception:
        return None, "unsafe_path"
    format_reason = validate_deliverable_file_for_delivery(resolved)
    if format_reason:
        return None, format_reason
    return str(resolved), ""


def _resolve_media_path(
    media_path: str,
    *,
    conversation_id: str,
    paths: RuntimePaths,
) -> tuple[str | None, str]:
    try:
        resolved = assert_safe_attachment_path(media_path, paths)
    except Exception:
        return None, "unsafe_path"
    stored_attachment = _stored_attachment_for_path(resolved, paths)
    if stored_attachment is not None and str(stored_attachment.get("conversation_id") or "") != conversation_id:
        return None, "cross_conversation"
    if _looks_like_stored_attachment_path(resolved, paths) and stored_attachment is None:
        return None, "missing_attachment"
    format_reason = validate_deliverable_file_for_delivery(resolved)
    if format_reason:
        return None, format_reason
    return str(resolved), ""


def _resolve_generated_delivery_path(
    media_path: str,
    *,
    conversation_id: str,
    paths: RuntimePaths,
) -> tuple[str | None, str]:
    try:
        resolved = assert_safe_attachment_path(media_path, paths)
    except Exception:
        return None, "unsafe_path"
    root = (
        paths.hermes_home
        / "cache"
        / "documents"
        / _safe_delivery_path_part(conversation_id or conversations.PERSONAL_CONVERSATION_ID)
    ).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except Exception:
        return None, "cross_conversation"
    if not resolved.is_file():
        return None, "missing_file"
    format_reason = validate_deliverable_file_for_delivery(resolved)
    if format_reason:
        return None, format_reason
    return str(resolved), ""


def _safe_delivery_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return cleaned[:80] or "conversation"


def _stored_attachment_for_path(path: Path, paths: RuntimePaths) -> dict[str, Any] | None:
    return conversations.find_attachment_by_safe_path(path, include_safe_path=True, paths=paths)


def _looks_like_stored_attachment_path(path: Path, paths: RuntimePaths) -> bool:
    try:
        is_safe_stored_attachment(path, paths)
        return True
    except Exception:
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


def _dedupe_media_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in items:
        path = str(item.get("path") or "")
        if not path:
            continue
        key = str(Path(path).resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append({"path": path, "media_kind": str(item.get("media_kind") or "document")})
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
        "missing_file": "没有找到要发送的文件。",
        "empty_file": "生成的文件是空的，已拒绝发送。",
        "file_too_large": "生成的文件超过 25 MB，暂时不能发送。",
        "invalid_file_name": "文件名不安全，已拒绝生成。",
        "missing_file_content": "没有收到要写入文件的内容。",
        "ambiguous_file_content": "文件内容只能使用文本或 base64 其中一种。",
        "invalid_base64": "文件内容不是有效的 base64。",
        "file_write_failed": "文件写入失败。",
        "invalid_file_format": "生成的文件格式和扩展名不一致，已拒绝发送。表格默认请生成 CSV；需要 Excel 时必须生成真实 .xlsx 文件。",
        "unsupported_generated_format": "这个格式暂时不能从纯文本直接生成。请改成 CSV、TXT、Markdown，或生成真实二进制文件后再发送。",
        "missing_file_path": "没有收到要发送的文件路径。",
        "missing_attachment": "没有找到要返还的附件。",
        "cross_conversation": "这个附件属于另一个对话，不能在当前对话里返还。",
        "adapter_unavailable": "当前发送通道不可用。",
        "unsupported_media": "这个媒体标记暂时不能作为附件返还。",
        "invalid_delivery_output": "附件返还需要走小黑子的结构化工具，不能把内部附件链接写在正文里。",
        "invalid_delivery_action": "附件返还动作格式不正确。",
        "delivery_action_failed": "附件返还动作没有成功。",
        "invalid_attachment_id": "附件编号不正确。已有附件必须使用 att_ 开头的真实附件编号；新生成文件需要先创建文件再交付。",
        "no_active_turn": "当前没有可用的附件返还上下文。",
    }.get(reason_code, "附件暂时不能返还。")
