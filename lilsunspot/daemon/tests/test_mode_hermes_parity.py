from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace


LOCAL_PROVIDER = {
    "id": "ollama",
    "type": "local",
    "env_key": "OLLAMA_API_KEY",
    "base_url": "http://127.0.0.1:11434/v1",
    "hermes_provider": "custom",
}


class FakeSessionDB:
    histories: dict[str, list[dict[str, str]]] = {}

    def get_messages_as_conversation(self, session_id, include_ancestors=False):
        return list(self.histories.get(session_id, []))


class CapturingAIAgent:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.model = kwargs["model"]
        self.provider = kwargs["provider"]

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


def _install_capture_agent(daemon_client, monkeypatch):
    CapturingAIAgent.calls = []
    FakeSessionDB.histories = {}
    monkeypatch.setattr(
        daemon_client.agent_runner,
        "_load_hermes_classes",
        lambda _paths: (CapturingAIAgent, FakeSessionDB),
    )


def _save_local_provider(daemon_client):
    daemon_client.hermes_runtime.save_provider_credentials(
        LOCAL_PROVIDER,
        "llama3.2",
        "",
        paths=daemon_client.config_paths.get_runtime_paths(),
    )


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate()


def test_all_modes_keep_agent_toolsets_memory_and_delivery_overlay(daemon_client, monkeypatch):
    _install_capture_agent(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="Mode parity", paths=paths)

    mode_cases = [
        ("balanced", {}),
        ("pragmatic", {}),
        ("emotional", {}),
        ("custom", {"style_axis": 15, "detail_level": 30, "autonomy_level": 80}),
    ]
    for mode, sliders in mode_cases:
        daemon_client.modes.select_mode(mode, paths, conversation_id=conversation["id"], scope="conversation", **sliders)
        asyncio.run(daemon_client.agent_runner.send_agent_message(f"消息 {mode}", conversation["id"], paths))

    assert len(CapturingAIAgent.calls) == len(mode_cases)
    toolsets_by_mode = [call["kwargs"]["enabled_toolsets"] for call in CapturingAIAgent.calls]
    assert all(toolsets == toolsets_by_mode[0] for toolsets in toolsets_by_mode)
    enabled = set(toolsets_by_mode[0])
    assert {"file", "memory", "session_search", "skills", "clarify", "lilsunspot_delivery", "lilsunspot_mode"} <= enabled
    for call in CapturingAIAgent.calls:
        kwargs = call["kwargs"]
        assert kwargs["skip_memory"] is False
        assert kwargs["skip_context_files"] is True
        assert kwargs["load_soul_identity"] is True
        assert "lilsunspot_deliver_file" in kwargs["ephemeral_system_prompt"]
        assert "当前 lilsunspot 能力状态快照" in kwargs["ephemeral_system_prompt"]


def test_required_file_toolset_matches_config_capability_and_agent_runtime(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()

    saved = daemon_client.capabilities.save_platform_toolsets(["memory", "session_search"], paths)
    file_capability = next(item for item in saved["available_toolsets"] if item["id"] == "toolset.file")

    assert "file" in saved["enabled_toolsets"]
    assert set(daemon_client.capabilities.enabled_toolsets_for_agent(paths)) == {"file", "memory", "session_search"}
    assert file_capability["enabled"] is True
    assert file_capability["status"] in {"enabled", "blocked"}
    runtime_toolsets = daemon_client.agent_runner._enabled_toolsets_for_lilsunspot_agent(paths)
    assert {"file", "lilsunspot_delivery", "lilsunspot_mode"} <= set(runtime_toolsets)


def test_mode_control_events_do_not_pollute_history_and_reply_metadata_maps_messages(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    seen: dict[str, object] = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen["message"] = message
        seen["kwargs"] = kwargs
        return {
            "ok": True,
            "reply": "最终可见回复。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
            "hermes_session_id": conversation_id,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    sent = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "普通问题"},
    )
    assert sent.status_code == 200
    user_id = sent.json()["user_message"]["id"]
    assistant_id = sent.json()["assistant_message"]["id"]
    _wait_until(
        lambda: (
            daemon_client.conversations.get_message(assistant_id, paths=paths) or {}
        ).get("status") == "sent"
    )
    assistant = daemon_client.conversations.get_message(assistant_id, paths=paths)
    assert assistant["metadata"]["source_message_ids"] == [user_id]
    assert assistant["metadata"]["source_message_count"] == 1
    assert assistant["metadata"]["visible_reply"] == "最终可见回复。"
    assert seen["kwargs"]["exclude_message_ids"] == [user_id]

    daemon_client.conversations.create_message(
        conversation_id="personal",
        source="desktop",
        role="user",
        text="切换到务实模式",
        metadata={"kind": "mode_intent_user", "control_event": True},
        paths=paths,
    )
    daemon_client.conversations.create_message(
        conversation_id="personal",
        source="system",
        role="system",
        text="输出风格已切换。",
        metadata={"kind": "mode_intent", "control_event": True},
        paths=paths,
    )

    history = daemon_client.conversations.conversation_history_for_agent("personal", paths=paths)
    texts = [item["content"] for item in history]
    assert "普通问题" in texts
    assert "最终可见回复。" in texts
    assert "切换到务实模式" not in texts
    assert "输出风格已切换。" not in texts


def test_weixin_attachment_reply_metadata_maps_source_message(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    cache_dir = paths.hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_file = cache_dir / "parity-note.txt"
    source_file.write_text("第一行\n第二行", encoding="utf-8")

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        return {
            "ok": True,
            "reply": "我读到了附件。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
            "hermes_session_id": conversation_id,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    result = asyncio.run(
        daemon_client.gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="帮我看看这个文件",
                media_urls=[str(source_file)],
                media_types=["text/plain"],
                message_id="wx-parity-file",
            ),
            paths=paths,
        )
    )

    assert result["ok"] is True
    assistant = result["assistant_message"]
    user_message = next(
        item
        for item in daemon_client.conversations.list_messages(
            daemon_client.conversations.PERSONAL_CONVERSATION_ID,
            paths=paths,
        )
        if item["role"] == "user" and item["metadata"].get("message_id") == "wx-parity-file"
    )
    assert assistant["metadata"]["source_message_ids"] == [user_message["id"]]
    assert assistant["metadata"]["source_message_count"] == 1
    assert assistant["metadata"]["visible_reply"] == "我读到了附件。"


def test_product_memories_are_explicit_local_records_not_hermes_memory(daemon_client):
    created = daemon_client.client.post(
        "/memory",
        headers=daemon_client.headers,
        json={"text": "喜欢短回复"},
    )
    assert created.status_code == 200
    memory = created.json()["memory"]
    assert memory["memory_scope"] == "local_record"
    assert memory["scope_label"] == "本地记录"
    assert memory["agent_memory_synced"] is False
    assert memory["metadata"]["agent_memory_synced"] is False

    listed = daemon_client.client.get("/memory", headers=daemon_client.headers)
    assert listed.status_code == 200
    listed_memory = listed.json()["memories"][0]
    assert listed_memory["scope_label"] == "本地记录"
    assert listed_memory["agent_memory_synced"] is False

    capabilities = daemon_client.client.get("/capabilities", headers=daemon_client.headers).json()["capabilities"]
    prompt_injection = next(item for item in capabilities if item["id"] == "product.memory.prompt_injection")
    assert prompt_injection["enabled"] is False
    assert prompt_injection["source_of_truth"] == "not implemented"


def test_mode_modules_do_not_construct_provider_http_requests():
    from pathlib import Path

    import lilsunspot.daemon.mode_intents as mode_intents
    import lilsunspot.daemon.mode_runtime_policy as mode_runtime_policy
    import lilsunspot.daemon.mode_tools as mode_tools
    import lilsunspot.daemon.modes as modes

    for module in [mode_intents, mode_runtime_policy, mode_tools, modes]:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "chat/completions" not in source
        assert "responses.create" not in source
        assert "Anthropic" not in source
        assert "httpx" not in source
