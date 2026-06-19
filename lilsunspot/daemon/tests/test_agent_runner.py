from __future__ import annotations

import asyncio


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
    assert "当前输出模式" in system_prompt
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
    assert "当前输出模式：pragmatic" in first["ephemeral_system_prompt"]
    assert "当前输出模式：emotional" in second["ephemeral_system_prompt"]
    assert "当前 lilsunspot 能力状态快照" in first["ephemeral_system_prompt"]
    assert "当前 lilsunspot 能力状态快照" in second["ephemeral_system_prompt"]


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
