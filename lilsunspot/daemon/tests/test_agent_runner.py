from __future__ import annotations

import asyncio
import threading
import time


LOCAL_PROVIDER = {
    "id": "ollama",
    "type": "local",
    "env_key": "OLLAMA_API_KEY",
    "base_url": "http://127.0.0.1:11434/v1",
    "hermes_provider": "custom",
}


class FakeSessionDB:
    histories: dict[str, list[dict[str, str]]] = {}
    history_requests: list[str] = []
    deleted: list[str] = []

    def get_messages_as_conversation(self, session_id, include_ancestors=False):
        self.history_requests.append(session_id)
        return list(self.histories.get(session_id, []))

    def delete_session(self, session_id, sessions_dir=None):
        self.deleted.append(session_id)
        return True


class FakeAIAgent:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.model = kwargs["model"]
        self.provider = kwargs["provider"]
        self.base_url = kwargs["base_url"]

    def run_conversation(self, user_message, conversation_history=None, task_id=None):
        self.calls.append(
            {
                "kwargs": self.kwargs,
                "user_message": user_message,
                "history": list(conversation_history or []),
                "task_id": task_id,
            }
        )
        return {
            "final_response": f"reply:{user_message}",
            "messages": [
                *(conversation_history or []),
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"reply:{user_message}"},
            ],
            "api_calls": 1,
            "model": self.model,
            "provider": self.provider,
        }


def _install_fake_hermes(daemon_client, monkeypatch):
    FakeSessionDB.histories = {}
    FakeSessionDB.history_requests = []
    FakeSessionDB.deleted = []
    FakeAIAgent.calls = []

    def fake_load_classes(paths):
        return FakeAIAgent, FakeSessionDB

    monkeypatch.setattr(daemon_client.agent_runner, "_load_hermes_classes", fake_load_classes)


def _save_local_provider(daemon_client):
    daemon_client.hermes_runtime.save_provider_credentials(
        LOCAL_PROVIDER,
        "llama3.2",
        "",
        paths=daemon_client.config_paths.get_runtime_paths(),
    )


def test_agent_runner_uses_independent_hermes_sessions_per_conversation(daemon_client, monkeypatch):
    _install_fake_hermes(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    first = daemon_client.conversations.create_conversation(title="A", paths=paths)
    second = daemon_client.conversations.create_conversation(title="B", paths=paths)

    result_a = asyncio.run(daemon_client.agent_runner.send_agent_message("第一条", first["id"], paths))
    result_b = asyncio.run(daemon_client.agent_runner.send_agent_message("第二条", second["id"], paths))

    assert result_a["engine"] == "hermes_agent_loop"
    assert result_b["engine"] == "hermes_agent_loop"
    assert result_a["conversation_id"] == first["id"]
    assert result_b["conversation_id"] == second["id"]
    assert [call["task_id"] for call in FakeAIAgent.calls] == [first["id"], second["id"]]
    assert FakeAIAgent.calls[0]["kwargs"]["session_id"] == first["id"]
    assert FakeAIAgent.calls[1]["kwargs"]["session_id"] == second["id"]
    assert FakeAIAgent.calls[0]["kwargs"]["ephemeral_system_prompt"]
    system_prompt = FakeAIAgent.calls[0]["kwargs"]["ephemeral_system_prompt"]
    assert "你是 Lilsunspot 小黑子" in system_prompt
    assert "当前 lilsunspot 能力状态快照" in system_prompt
    assert "当前表达风格" in system_prompt
    assert "用户要求生成新文件" in system_prompt
    assert FakeAIAgent.calls[0]["kwargs"]["skip_memory"] is False
    assert FakeAIAgent.calls[0]["kwargs"]["skip_context_files"] is True
    assert FakeAIAgent.calls[0]["kwargs"]["load_soul_identity"] is True


def test_agent_runner_mode_overlay_does_not_change_tools_memory_or_soul(daemon_client, monkeypatch):
    _install_fake_hermes(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="Mode parity", paths=paths)

    daemon_client.modes.select_mode("pragmatic", paths)
    asyncio.run(daemon_client.agent_runner.send_agent_message("第一轮", conversation["id"], paths))
    daemon_client.modes.select_mode("emotional", paths)
    asyncio.run(daemon_client.agent_runner.send_agent_message("第二轮", conversation["id"], paths))

    first = FakeAIAgent.calls[-2]["kwargs"]
    second = FakeAIAgent.calls[-1]["kwargs"]
    assert first["enabled_toolsets"] == second["enabled_toolsets"]
    assert first["skip_memory"] is False
    assert second["skip_memory"] is False
    assert first["skip_context_files"] is True
    assert second["skip_context_files"] is True
    assert first["load_soul_identity"] is True
    assert second["load_soul_identity"] is True
    assert "当前表达风格：pragmatic" in first["ephemeral_system_prompt"]
    assert "当前表达风格：emotional" in second["ephemeral_system_prompt"]
    assert "当前 lilsunspot 能力状态快照" in first["ephemeral_system_prompt"]
    assert "当前 lilsunspot 能力状态快照" in second["ephemeral_system_prompt"]


def test_expression_sliders_do_not_change_generation_runtime_limits(daemon_client, monkeypatch):
    _install_fake_hermes(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="Mode runtime", paths=paths)

    daemon_client.modes.select_mode(
        "custom",
        paths,
        style_axis=10,
        detail_level=20,
        autonomy_level=10,
        conversation_id=conversation["id"],
        scope="conversation",
    )
    asyncio.run(daemon_client.agent_runner.send_agent_message("低自主", conversation["id"], paths))

    daemon_client.modes.select_mode(
        "custom",
        paths,
        style_axis=80,
        detail_level=85,
        autonomy_level=85,
        conversation_id=conversation["id"],
        scope="conversation",
    )
    asyncio.run(daemon_client.agent_runner.send_agent_message("高自主", conversation["id"], paths))

    low = FakeAIAgent.calls[-2]["kwargs"]
    high = FakeAIAgent.calls[-1]["kwargs"]
    assert low["max_tokens"] == high["max_tokens"] == 1200
    assert low["max_iterations"] == high["max_iterations"] == 24
    assert low["reasoning_config"] == high["reasoning_config"] == {"enabled": True, "effort": "medium"}
    assert "目标约" not in low["ephemeral_system_prompt"]
    assert "本轮最多" not in high["ephemeral_system_prompt"]
    assert "当前表达风格：custom" in low["ephemeral_system_prompt"]
    assert "当前表达风格：custom" in high["ephemeral_system_prompt"]
    assert low["enabled_toolsets"] == high["enabled_toolsets"]


def test_agent_runner_host_callbacks_update_phase_and_control_active_turn(daemon_client, monkeypatch):
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="Host callbacks", paths=paths)
    assistant = daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="assistant",
        role="assistant",
        text="正在回复...",
        status="generating",
        paths=paths,
    )
    seen: dict[str, object] = {}

    class CallbackAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.model = kwargs["model"]
            self.provider = kwargs["provider"]
            self.interrupts: list[str] = []
            self.steers: list[str] = []
            seen["agent"] = self

        def interrupt(self, message=None):
            self.interrupts.append(message)

        def steer(self, text):
            self.steers.append(text)
            return True

        def run_conversation(self, user_message, conversation_history=None, task_id=None):
            stop_result = daemon_client.agent_host.interrupt_active_turn(conversation["id"], "请停止")
            steer_result = daemon_client.agent_host.steer_active_turn(conversation["id"], "补充一点上下文")
            assert stop_result["ok"] is True
            assert steer_result["ok"] is True
            self.kwargs["status_callback"]("lifecycle", "正在分析任务")
            self.kwargs["tool_start_callback"]("tool-1", "lilsunspot_get_mode", {})
            self.kwargs["tool_complete_callback"]("tool-1", "lilsunspot_get_mode", {}, "{}")
            self.kwargs["stream_delta_callback"]("片段不应写入消息")
            return {
                "final_response": f"reply:{user_message}",
                "messages": [],
                "api_calls": 1,
                "model": self.model,
                "provider": self.provider,
            }

    monkeypatch.setattr(
        daemon_client.agent_runner,
        "_load_hermes_classes",
        lambda _paths: (CallbackAIAgent, FakeSessionDB),
    )

    result = asyncio.run(
        daemon_client.agent_runner.send_agent_message(
            "需要工具",
            conversation["id"],
            paths,
            host_message_id=assistant["id"],
        )
    )

    assert result["ok"] is True
    agent = seen["agent"]
    assert agent.interrupts == ["请停止"]
    assert agent.steers == ["补充一点上下文"]
    updated = daemon_client.conversations.get_message(assistant["id"], paths=paths)
    assert updated["status"] == "generating"
    assert updated["text"] == "正在整理回复..."
    assert updated["metadata"]["host_status"]["phase"] == "streaming"
    events = daemon_client.conversations.list_events_after(0, paths=paths)
    assert any(event["event"] == "agent.interrupt.requested" for event in events)
    assert any(event["event"] == "agent.steer.received" for event in events)
    assert any(event["event"] == "agent.status" and event["data"]["phase"] == "tool_complete" for event in events)
    assert daemon_client.agent_host.interrupt_active_turn(conversation["id"], "再停一次")["ok"] is False


def test_agent_runner_clarify_callback_completes_desktop_question_answer(daemon_client, monkeypatch):
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="Clarify desktop", paths=paths)
    assistant = daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="assistant",
        role="assistant",
        text="正在回复...",
        status="generating",
        paths=paths,
    )
    result_holder: dict[str, object] = {}

    class ClarifyAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.model = kwargs["model"]
            self.provider = kwargs["provider"]

        def run_conversation(self, user_message, conversation_history=None, task_id=None):
            answer = self.kwargs["clarify_callback"]("请选择执行路线", ["先整理", "直接执行"])
            return {
                "final_response": f"收到：{answer}",
                "messages": [],
                "api_calls": 1,
                "model": self.model,
                "provider": self.provider,
            }

    monkeypatch.setattr(
        daemon_client.agent_runner,
        "_load_hermes_classes",
        lambda _paths: (ClarifyAIAgent, FakeSessionDB),
    )
    monkeypatch.setattr(
        daemon_client.generation_controls,
        "_model_metadata",
        lambda _provider, _hermes_provider, _model: (None, None),
    )
    # Load the upstream callback context outside the timed handoff assertion.
    # Its first import performs plugin discovery, which is unrelated to clarify.
    import gateway.session_context  # noqa: F401
    import tools.approval  # noqa: F401

    def run_turn():
        result_holder["result"] = asyncio.run(
            daemon_client.agent_runner.send_agent_message(
                "需要确认",
                conversation["id"],
                paths,
                host_message_id=assistant["id"],
            )
        )

    worker = threading.Thread(target=run_turn, daemon=True)
    worker.start()
    # This assertion exercises the clarify handoff, not Hermes cold-start latency.
    # Plugin discovery and models.dev cache initialization can exceed three
    # seconds in a fresh Windows process before the fake agent is constructed.
    deadline = time.time() + 15
    pending = None
    while time.time() < deadline and worker.is_alive():
        pending = daemon_client.agent_host.pending_clarify_for_conversation(conversation["id"])
        if pending:
            break
        time.sleep(0.02)
    assert pending is not None, result_holder.get("result")
    question_message = daemon_client.conversations.get_message(pending["message_id"], paths=paths)
    assert "请选择执行路线" in question_message["text"]
    assert question_message["metadata"]["clarify"]["status"] == "waiting"

    response = daemon_client.client.post(
        f"/conversations/{conversation['id']}/messages",
        headers=daemon_client.headers,
        json={"message": "先整理"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert body["chat"]["clarify_answer"] is True
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert result_holder["result"]["reply"] == "收到：先整理"
    answer_message = daemon_client.conversations.get_message(body["user_message"]["id"], paths=paths)
    assert answer_message["metadata"]["kind"] == "clarify_answer"
    answered = daemon_client.conversations.get_message(assistant["id"], paths=paths)
    assert answered["metadata"]["clarify"]["status"] == "answered"


def test_agent_runner_falls_back_to_lilsunspot_mirror_only_when_hermes_history_empty(daemon_client, monkeypatch):
    _install_fake_hermes(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="旧对话", paths=paths)
    daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="desktop",
        role="user",
        text="上一轮用户",
        emit_event=False,
        paths=paths,
    )
    daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="assistant",
        role="assistant",
        text="上一轮助手",
        emit_event=False,
        paths=paths,
    )
    current = daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="desktop",
        role="user",
        text="当前用户",
        emit_event=False,
        paths=paths,
    )

    result = asyncio.run(
        daemon_client.agent_runner.send_agent_message(
            "当前用户",
            conversation["id"],
            paths,
            current_message_id=current["id"],
        )
    )

    assert result["ok"] is True
    assert FakeAIAgent.calls[-1]["history"] == [
        {"role": "user", "content": "上一轮用户"},
        {"role": "assistant", "content": "上一轮助手"},
    ]

    FakeSessionDB.histories[conversation["id"]] = [{"role": "user", "content": "Hermes 已有历史"}]
    asyncio.run(daemon_client.agent_runner.send_agent_message("下一轮", conversation["id"], paths))

    assert FakeAIAgent.calls[-1]["history"] == [{"role": "user", "content": "Hermes 已有历史"}]


def test_delete_conversation_removes_hermes_session(daemon_client, monkeypatch):
    _install_fake_hermes(daemon_client, monkeypatch)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="可删除", paths=paths)
    daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="desktop",
        role="user",
        text="待删除",
        emit_event=False,
        paths=paths,
    )

    response = daemon_client.client.delete(f"/conversations/{conversation['id']}", headers=daemon_client.headers)

    assert response.status_code == 200
    assert response.json()["hermes_deleted"] is True
    assert FakeSessionDB.deleted == [conversation["id"]]
    assert daemon_client.conversations.list_messages(conversation["id"], paths=paths) == []
