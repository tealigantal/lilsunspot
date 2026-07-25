from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import Any

from . import conversations
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .attachments import AttachmentError
from .media_delivery import add_delivery_context_to_prompt, prepare_assistant_delivery, register_prepared_delivery


TEXT_BATCH_DELAY_SECONDS = 3.0
TEXT_BATCH_MAX_MESSAGES = 8
TEXT_BATCH_MAX_CHARS = 4000

logger = logging.getLogger(__name__)


@dataclass
class _BatchItem:
    text: str
    message_id: str | None


@dataclass
class _TextTurnBatch:
    key: str
    conversation_id: str
    assistant_message_id: str
    assistant_message: dict[str, Any]
    assistant_source: str
    route: dict[str, str] | None
    generation_override: dict[str, Any] | None
    paths: RuntimePaths
    future: Future
    items: list[_BatchItem] = field(default_factory=list)
    char_count: int = 0
    last_updated: float = field(default_factory=time.monotonic)
    sealed: bool = False

    def can_accept(self, text: str) -> bool:
        if self.sealed or self.generation_override is not None:
            return False
        if len(self.items) >= TEXT_BATCH_MAX_MESSAGES:
            return False
        return self.char_count + len(text) <= TEXT_BATCH_MAX_CHARS

    def add(self, text: str, message_id: str | None) -> None:
        self.items.append(_BatchItem(text=text, message_id=message_id))
        self.char_count += len(text)
        self.last_updated = time.monotonic()
        if len(self.items) >= TEXT_BATCH_MAX_MESSAGES or self.char_count >= TEXT_BATCH_MAX_CHARS:
            self.sealed = True


_LOCK = RLock()
_QUEUES: dict[str, deque[_TextTurnBatch]] = {}
_WORKERS: dict[str, Future] = {}
_BACKGROUND_LOOP: asyncio.AbstractEventLoop | None = None
_BACKGROUND_THREAD: Thread | None = None


def key_for_desktop(conversation_id: str) -> str:
    return f"desktop:{conversation_id.strip() or conversations.PERSONAL_CONVERSATION_ID}"


def key_for_weixin(route: dict[str, str] | None, conversation_id: str) -> str:
    route_key = conversations.weixin_route_key(route or {})
    return f"weixin:{route_key or conversation_id.strip() or conversations.PERSONAL_CONVERSATION_ID}"


def reset_for_tests() -> None:
    with _LOCK:
        for worker in _WORKERS.values():
            if not worker.done():
                worker.cancel()
        _WORKERS.clear()
        _QUEUES.clear()


async def enqueue_text_turn(
    *,
    key: str,
    conversation_id: str,
    text: str,
    current_message_id: str | None,
    assistant_source: str,
    paths: RuntimePaths | None = None,
    route: dict[str, str] | None = None,
    generation_override: dict[str, Any] | None = None,
    wait_for_reply: bool = False,
) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    text_value = text.strip()
    if not text_value:
        return {
            "accepted": False,
            "ok": False,
            "message": "消息内容不能为空。",
            "suppressed": True,
        }

    enqueue_result = _enqueue(
        key=key,
        conversation_id=conversation_id,
        text=text_value,
        current_message_id=current_message_id,
        assistant_source=assistant_source,
        paths=runtime_paths,
        route=route,
        generation_override=generation_override,
    )
    if wait_for_reply and enqueue_result.get("owner"):
        return await asyncio.wrap_future(enqueue_result["future"])
    if wait_for_reply:
        return {
            "accepted": True,
            "ok": True,
            "suppressed": True,
            "message": "",
            "assistant_message": enqueue_result.get("assistant_message"),
        }
    return {key: value for key, value in enqueue_result.items() if key != "future"}


def _enqueue(
    *,
    key: str,
    conversation_id: str,
    text: str,
    current_message_id: str | None,
    assistant_source: str,
    paths: RuntimePaths,
    route: dict[str, str] | None,
    generation_override: dict[str, Any] | None,
) -> dict[str, Any]:
    with _LOCK:
        queue = _QUEUES.setdefault(key, deque())
        if queue:
            candidate = queue[-1]
            if generation_override is None and candidate.can_accept(text):
                candidate.add(text, current_message_id)
                assistant = conversations.get_message(candidate.assistant_message_id, paths) or candidate.assistant_message
                return {
                    "accepted": True,
                    "owner": False,
                    "suppressed": True,
                    "turn_id": candidate.assistant_message_id,
                    "assistant_message": assistant,
                }

        if conversations.get_conversation(conversation_id, paths) is None:
            if not queue:
                _QUEUES.pop(key, None)
            return {
                "accepted": False,
                "owner": False,
                "suppressed": True,
                "cancelled": True,
                "message": "",
            }

        assistant_message = conversations.create_message(
            conversation_id=conversation_id,
            source=assistant_source,
            role="assistant",
            text="正在回复...",
            status="generating",
            metadata={
                "kind": "chat_reply_pending",
                "in_reply_to": current_message_id,
                "batch_key": key,
            },
            paths=paths,
        )
        batch = _TextTurnBatch(
            key=key,
            conversation_id=conversation_id,
            assistant_message_id=assistant_message["id"],
            assistant_message=assistant_message,
            assistant_source=assistant_source,
            route=route,
            generation_override=generation_override,
            paths=paths,
            future=Future(),
        )
        batch.add(text, current_message_id)
        if generation_override is not None:
            batch.sealed = True
        queue.append(batch)
        _start_worker_locked(key)
        return {
            "accepted": True,
            "owner": True,
            "suppressed": False,
            "turn_id": batch.assistant_message_id,
            "assistant_message": assistant_message,
            "future": batch.future,
        }


def _start_worker_locked(key: str) -> None:
    worker = _WORKERS.get(key)
    if worker is not None and not worker.done():
        return
    _WORKERS[key] = asyncio.run_coroutine_threadsafe(_worker(key), _background_loop())


def _background_loop() -> asyncio.AbstractEventLoop:
    global _BACKGROUND_LOOP, _BACKGROUND_THREAD
    with _LOCK:
        if _BACKGROUND_LOOP is not None and _BACKGROUND_LOOP.is_running():
            return _BACKGROUND_LOOP
        loop = asyncio.new_event_loop()
        thread = Thread(target=_run_background_loop, args=(loop,), name="lilsunspot-turn-coalescer", daemon=True)
        _BACKGROUND_LOOP = loop
        _BACKGROUND_THREAD = thread
        thread.start()
        return loop


def _run_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


async def _worker(key: str) -> None:
    try:
        while True:
            with _LOCK:
                queue = _QUEUES.get(key)
                if not queue:
                    _QUEUES.pop(key, None)
                    _WORKERS.pop(key, None)
                    return
                batch = queue[0]
            await _wait_until_ready(batch)
            await _run_batch(batch)
            with _LOCK:
                queue = _QUEUES.get(key)
                if queue and queue[0] is batch:
                    queue.popleft()
                if not queue:
                    _QUEUES.pop(key, None)
                    _WORKERS.pop(key, None)
                    return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Text turn coalescer failed key=%s error=%s", key, type(exc).__name__)
        with _LOCK:
            queue = _QUEUES.pop(key, None)
            _WORKERS.pop(key, None)
        for batch in list(queue or []):
            _set_future_result(batch, _cancelled_result())


async def _wait_until_ready(batch: _TextTurnBatch) -> None:
    while True:
        with _LOCK:
            if batch.sealed:
                return
            remaining = batch.last_updated + TEXT_BATCH_DELAY_SECONDS - time.monotonic()
            if remaining <= 0:
                batch.sealed = True
                return
        await asyncio.sleep(min(max(remaining, 0.01), 0.1))


async def _run_batch(batch: _TextTurnBatch) -> None:
    if conversations.get_conversation(batch.conversation_id, batch.paths) is None:
        _set_future_result(batch, _cancelled_result())
        return

    prompt = add_delivery_context_to_prompt(
        _build_prompt([item.text for item in batch.items]),
        conversation_id=batch.conversation_id,
        paths=batch.paths,
    )
    message_ids = [item.message_id for item in batch.items if item.message_id]
    current_message_id = message_ids[-1] if message_ids else None
    try:
        from . import agent_runner

        chat_result = await agent_runner.send_agent_message(
            prompt,
            batch.conversation_id,
            batch.paths,
            current_message_id=current_message_id,
            host_message_id=batch.assistant_message_id,
            exclude_message_ids=message_ids,
            route=batch.route,
            generation_override=batch.generation_override,
            require_existing_conversation=True,
        )
    except Exception as exc:
        logger.exception("Coalesced Hermes turn failed conversation=%s error=%s", batch.conversation_id, type(exc).__name__)
        chat_result = {
            "ok": False,
            "error_code": "unknown",
            "message": "请求失败，请稍后再试。",
            "suggestion": "请重新检查 AI 服务设置。",
        }

    if chat_result.get("cancelled") or conversations.get_conversation(batch.conversation_id, batch.paths) is None:
        _set_future_result(batch, _cancelled_result(chat_result))
        return

    if chat_result.get("ok"):
        prepared = prepare_assistant_delivery(
            str(chat_result.get("reply") or ""),
            conversation_id=batch.conversation_id,
            paths=batch.paths,
            delivery_actions=chat_result.get("delivery_actions") if isinstance(chat_result.get("delivery_actions"), list) else [],
            include_outbound_media=bool(batch.route),
        )
        delivery_metadata = prepared.metadata()
        updated = conversations.update_message(
            batch.assistant_message_id,
            text=prepared.visible_text,
            status="sent",
            metadata_patch={
                "kind": "chat_reply",
                "engine": chat_result.get("engine"),
                "provider": chat_result.get("provider"),
                "model": chat_result.get("model"),
                "hermes_session_id": chat_result.get("hermes_session_id"),
                "batch_count": len(batch.items),
                "source_message_ids": message_ids,
                "source_message_count": len(message_ids),
                "visible_reply": prepared.visible_text,
                "delivery": delivery_metadata,
                "generation_execution": chat_result.get("generation_execution"),
            },
            paths=batch.paths,
        )
        if updated is None:
            _set_future_result(batch, _cancelled_result(chat_result))
            return
        try:
            register_prepared_delivery(
                prepared,
                message_id=batch.assistant_message_id,
                conversation_id=batch.conversation_id,
                source="assistant_delivery",
                paths=batch.paths,
            )
        except AttachmentError:
            updated = conversations.update_message(
                batch.assistant_message_id,
                metadata_patch={
                    "delivery": {
                        "status": "rejected",
                        "delivered_count": 0,
                        "rejected_count": max(1, prepared.rejected_count),
                        "reason_code": "unsafe_path",
                    }
                },
                paths=batch.paths,
            ) or updated
            prepared.outbound_text = prepared.visible_text
            prepared.media_paths = []
            prepared.media_items = []
        updated = conversations.get_message(batch.assistant_message_id, paths=batch.paths) or updated
        next_chat = {
            **chat_result,
            "reply": prepared.visible_text,
            "visible_reply": prepared.visible_text,
            "_delivery_media": list(prepared.media_items) if batch.route else [],
            "_delivery_media_paths": list(prepared.media_paths) if batch.route else [],
        }
        next_chat.pop("delivery_actions", None)
        _set_future_result(
            batch,
            {
                "accepted": True,
                "ok": True,
                "suppressed": False,
                "message": "回复已生成。",
                "assistant_message": updated,
                "chat": next_chat,
            },
        )
        return

    error_text = _error_text(chat_result)
    updated = conversations.update_message(
        batch.assistant_message_id,
        text=error_text,
        status="error",
        metadata_patch={
            "kind": "chat_error",
            "error_code": chat_result.get("error_code"),
            "batch_count": len(batch.items),
            "generation_execution": chat_result.get("generation_execution"),
        },
        paths=batch.paths,
    )
    if updated is None:
        _set_future_result(batch, _cancelled_result(chat_result))
        return
    _set_future_result(
        batch,
        {
            "accepted": True,
            "ok": False,
            "suppressed": False,
            "message": str(chat_result.get("message") or "请求失败，请稍后再试。"),
            "assistant_message": updated,
            "chat": chat_result,
        },
    )


def _build_prompt(messages: list[str]) -> str:
    clean = [item.strip() for item in messages if item.strip()]
    if not clean:
        return "用户发来了一条空消息。"
    if len(clean) == 1:
        return clean[0][:TEXT_BATCH_MAX_CHARS]

    header = f"用户在短时间内连续发送了 {len(clean)} 条消息，请作为一个整体处理："
    lines = [header]
    remaining = TEXT_BATCH_MAX_CHARS - len(header) - 1
    for index, item in enumerate(clean, start=1):
        prefix = f"{index}. "
        if remaining <= len(prefix):
            break
        value = item[: max(0, remaining - len(prefix))]
        lines.append(f"{prefix}{value}")
        remaining -= len(prefix) + len(value) + 1
    return "\n".join(lines)


def _error_text(result: dict[str, Any]) -> str:
    message = str(result.get("message") or "请求失败，请稍后再试。").strip()
    suggestion = str(result.get("suggestion") or "").strip()
    return f"{message}\n{suggestion}".strip()


def _cancelled_result(chat_result: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "accepted": True,
        "ok": False,
        "suppressed": True,
        "cancelled": True,
        "message": "",
        "chat": chat_result or {"ok": False, "cancelled": True, "message": ""},
    }


def _set_future_result(batch: _TextTurnBatch, result: dict[str, Any]) -> None:
    if not batch.future.done():
        batch.future.set_result(result)
