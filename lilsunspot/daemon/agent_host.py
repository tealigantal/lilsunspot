from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import conversations
from .config_paths import RuntimePaths


CLARIFY_TIMEOUT_SECONDS = 300.0
_ACTIVE_LOCK = threading.RLock()
_ACTIVE_TURNS: dict[str, "ActiveTurn"] = {}
_PENDING_CLARIFY: dict[str, "PendingClarify"] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, *, max_chars: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > max_chars:
        return f"{text[:max_chars]}..."
    return text


def _format_tool_name(name: str) -> str:
    value = _clean_text(name, max_chars=60)
    return value or "工具"


def _clarify_text(question: str, choices: list[str] | None) -> str:
    lines = ["需要你确认一个问题：", question.strip()]
    if choices:
        lines.append("")
        lines.append("可选项：")
        for index, choice in enumerate(choices[:4], start=1):
            lines.append(f"{index}. {choice}")
        lines.append("也可以直接输入其他答案。")
    return "\n".join(lines)


@dataclass
class ActiveTurn:
    conversation_id: str
    agent: Any
    message_id: str | None
    paths: RuntimePaths
    started_at: str


@dataclass
class PendingClarify:
    conversation_id: str
    message_id: str
    question: str
    choices: list[str] | None
    paths: RuntimePaths
    event: threading.Event
    answer: str | None = None
    answer_message_id: str | None = None
    created_at: str = ""


class AgentHostCallbacks:
    def __init__(
        self,
        *,
        conversation_id: str,
        message_id: str | None,
        source: str,
        paths: RuntimePaths,
    ) -> None:
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.source = source or "assistant"
        self.paths = paths
        self._tool_iterations = 0
        self._tool_iterations_lock = threading.Lock()

    @property
    def tool_iterations(self) -> int:
        with self._tool_iterations_lock:
            return self._tool_iterations

    def status_callback(self, kind: str, message: str) -> None:
        label = _clean_text(message) or "正在处理当前任务..."
        self._record_phase("status", f"正在处理：{label}", status_kind=_clean_text(kind, max_chars=40), status_message=label)

    def stream_delta_callback(self, _delta: str) -> None:
        self._record_phase("streaming", "正在整理回复...")

    def tool_progress_callback(self, event: str, name: str, _preview: str | None = None, _args: Any = None) -> None:
        if str(event or "") == "tool.started":
            self._record_phase("tool_started", f"正在使用工具：{_format_tool_name(name)}...", tool=_format_tool_name(name))

    def tool_start_callback(self, tool_call_id: str, name: str, _args: Any) -> None:
        with self._tool_iterations_lock:
            self._tool_iterations += 1
        self._record_phase(
            "tool_started",
            f"正在使用工具：{_format_tool_name(name)}...",
            tool=_format_tool_name(name),
            tool_call_id=_clean_text(tool_call_id, max_chars=80),
        )

    def tool_complete_callback(self, tool_call_id: str, name: str, _args: Any, _result: Any) -> None:
        self._record_phase(
            "tool_complete",
            f"工具 {_format_tool_name(name)} 执行完成，正在整理回复...",
            tool=_format_tool_name(name),
            tool_call_id=_clean_text(tool_call_id, max_chars=80),
        )

    def clarify_callback(self, question: str, choices: list[str] | None = None) -> str:
        question_text = _clean_text(question, max_chars=800)
        if not question_text:
            raise ValueError("确认问题不能为空。")
        normalized_choices = [_clean_text(choice, max_chars=160) for choice in (choices or []) if _clean_text(choice, max_chars=160)]
        if not normalized_choices:
            normalized_choices = None

        message_id = self.message_id
        visible_text = _clarify_text(question_text, normalized_choices)
        if message_id:
            updated = conversations.update_message(
                message_id,
                text=visible_text,
                status="generating",
                metadata_patch={
                    "kind": "clarify_request",
                    "host_status": {
                        "phase": "clarify",
                        "message": "等待用户确认",
                        "updated_at": _now_iso(),
                    },
                    "clarify": {
                        "status": "waiting",
                        "question": question_text,
                        "choices": normalized_choices,
                    },
                },
                paths=self.paths,
            )
            if updated is None:
                message_id = None
        if not message_id:
            created = conversations.create_message(
                conversation_id=self.conversation_id,
                source=self.source,
                role="assistant",
                text=visible_text,
                status="generating",
                metadata={
                    "kind": "clarify_request",
                    "host_status": {
                        "phase": "clarify",
                        "message": "等待用户确认",
                        "updated_at": _now_iso(),
                    },
                    "clarify": {
                        "status": "waiting",
                        "question": question_text,
                        "choices": normalized_choices,
                    },
                },
                paths=self.paths,
            )
            message_id = created["id"]
            self.message_id = message_id

        pending = PendingClarify(
            conversation_id=self.conversation_id,
            message_id=message_id,
            question=question_text,
            choices=normalized_choices,
            paths=self.paths,
            event=threading.Event(),
            created_at=_now_iso(),
        )
        with _ACTIVE_LOCK:
            existing = _PENDING_CLARIFY.get(self.conversation_id)
            if existing and not existing.event.is_set():
                raise RuntimeError("上一个确认问题还在等待回复。")
            _PENDING_CLARIFY[self.conversation_id] = pending

        conversations.append_event(
            "agent.clarify.requested",
            {
                "conversation_id": self.conversation_id,
                "message_id": message_id,
                "question": question_text,
                "choices": normalized_choices,
            },
            paths=self.paths,
        )
        if not pending.event.wait(CLARIFY_TIMEOUT_SECONDS):
            with _ACTIVE_LOCK:
                if _PENDING_CLARIFY.get(self.conversation_id) is pending:
                    _PENDING_CLARIFY.pop(self.conversation_id, None)
            conversations.update_message(
                message_id,
                text="等待确认超时，本轮任务已取消。",
                status="error",
                metadata_patch={
                    "host_status": {
                        "phase": "clarify_timeout",
                        "message": "等待确认超时",
                        "updated_at": _now_iso(),
                    },
                    "clarify": {
                        "status": "timeout",
                        "question": question_text,
                        "choices": normalized_choices,
                    },
                },
                paths=self.paths,
            )
            raise TimeoutError("等待用户确认超时。")
        return str(pending.answer or "").strip()

    def _record_phase(self, phase: str, visible_text: str, **metadata: Any) -> None:
        payload = {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "phase": phase,
            "updated_at": _now_iso(),
            **{key: value for key, value in metadata.items() if value not in (None, "")},
        }
        conversations.append_event("agent.status", payload, paths=self.paths)
        if self.message_id:
            conversations.update_message(
                self.message_id,
                text=visible_text,
                status="generating",
                metadata_patch={
                    "host_status": payload,
                },
                paths=self.paths,
            )


def register_active_turn(
    conversation_id: str,
    *,
    agent: Any,
    message_id: str | None,
    paths: RuntimePaths,
) -> None:
    with _ACTIVE_LOCK:
        _ACTIVE_TURNS[conversation_id] = ActiveTurn(
            conversation_id=conversation_id,
            agent=agent,
            message_id=message_id,
            paths=paths,
            started_at=_now_iso(),
        )


def clear_active_turn(conversation_id: str, agent: Any | None = None) -> None:
    with _ACTIVE_LOCK:
        active = _ACTIVE_TURNS.get(conversation_id)
        if active is None:
            return
        if agent is not None and active.agent is not agent:
            return
        _ACTIVE_TURNS.pop(conversation_id, None)


def interrupt_active_turn(conversation_id: str, message: str | None = None) -> dict[str, Any]:
    text = _clean_text(message, max_chars=240) or "用户停止了当前任务。"
    with _ACTIVE_LOCK:
        active = _ACTIVE_TURNS.get(conversation_id)
    if active is None:
        return {"ok": False, "message": "当前没有正在执行的任务。"}
    interrupt = getattr(active.agent, "interrupt", None)
    if not callable(interrupt):
        return {"ok": False, "message": "当前任务不支持停止。"}
    interrupt(text)
    if active.message_id:
        conversations.update_message(
            active.message_id,
            text="正在停止当前任务...",
            status="generating",
            metadata_patch={
                "host_status": {
                    "phase": "interrupt_requested",
                    "message": text,
                    "updated_at": _now_iso(),
                }
            },
            paths=active.paths,
        )
    conversations.append_event(
        "agent.interrupt.requested",
        {"conversation_id": conversation_id, "message_id": active.message_id},
        paths=active.paths,
    )
    return {"ok": True, "message": "已请求停止当前任务。"}


def steer_active_turn(conversation_id: str, text: str) -> dict[str, Any]:
    steer_text = _clean_text(text, max_chars=1200)
    if not steer_text:
        return {"ok": False, "message": "补充内容不能为空。"}
    with _ACTIVE_LOCK:
        active = _ACTIVE_TURNS.get(conversation_id)
    if active is None:
        return {"ok": False, "message": "当前没有正在执行的任务。"}
    steer = getattr(active.agent, "steer", None)
    if not callable(steer):
        return {"ok": False, "message": "当前任务不支持补充说明。"}
    accepted = bool(steer(steer_text))
    if not accepted:
        return {"ok": False, "message": "补充内容没有被当前任务接受。"}
    if active.message_id:
        conversations.update_message(
            active.message_id,
            text="已收到补充说明，我会并入当前任务...",
            status="generating",
            metadata_patch={
                "host_status": {
                    "phase": "steer_received",
                    "message": "已收到补充说明",
                    "updated_at": _now_iso(),
                }
            },
            paths=active.paths,
        )
    conversations.append_event(
        "agent.steer.received",
        {"conversation_id": conversation_id, "message_id": active.message_id},
        paths=active.paths,
    )
    return {"ok": True, "message": "已把补充说明加入当前任务。"}


def submit_clarify_answer(
    conversation_id: str,
    answer: str,
    *,
    message_id: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any] | None:
    answer_text = _clean_text(answer, max_chars=2000)
    if not answer_text:
        return None
    with _ACTIVE_LOCK:
        pending = _PENDING_CLARIFY.get(conversation_id)
        if pending is None or pending.event.is_set():
            return None
        _PENDING_CLARIFY.pop(conversation_id, None)
        pending.answer = answer_text
        pending.answer_message_id = message_id
    runtime_paths = paths or pending.paths
    assistant_message = None
    try:
        if message_id:
            conversations.update_message(
                message_id,
                metadata_patch={
                    "kind": "clarify_answer",
                    "clarify_request_id": pending.message_id,
                },
                paths=runtime_paths,
            )
        assistant_message = conversations.update_message(
            pending.message_id,
            text="已收到，我继续处理...",
            status="generating",
            metadata_patch={
                "host_status": {
                    "phase": "clarify_answered",
                    "message": "已收到用户确认",
                    "updated_at": _now_iso(),
                },
                "clarify": {
                    "status": "answered",
                    "question": pending.question,
                    "choices": pending.choices,
                    "answer_message_id": message_id,
                },
            },
            paths=runtime_paths,
        )
        conversations.append_event(
            "agent.clarify.answered",
            {
                "conversation_id": conversation_id,
                "message_id": pending.message_id,
                "answer_message_id": message_id,
            },
            paths=runtime_paths,
        )
    finally:
        pending.event.set()
    return {
        "ok": True,
        "message": "已收到，我继续处理。",
        "conversation_id": conversation_id,
        "question": pending.question,
        "answer": answer_text,
        "assistant_message": assistant_message,
    }


def pending_clarify_for_conversation(conversation_id: str) -> dict[str, Any] | None:
    with _ACTIVE_LOCK:
        pending = _PENDING_CLARIFY.get(conversation_id)
        if pending is None:
            return None
        return {
            "conversation_id": pending.conversation_id,
            "message_id": pending.message_id,
            "question": pending.question,
            "choices": pending.choices,
            "created_at": pending.created_at,
        }


def reset_for_tests() -> None:
    with _ACTIVE_LOCK:
        for pending in _PENDING_CLARIFY.values():
            pending.event.set()
        _ACTIVE_TURNS.clear()
        _PENDING_CLARIFY.clear()
