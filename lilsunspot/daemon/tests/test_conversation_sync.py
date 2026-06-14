from __future__ import annotations

import asyncio
import base64
import re
import time
from types import SimpleNamespace


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate()


def test_conversation_crud_archive_and_delete_cascade(daemon_client, monkeypatch):
    monkeypatch.setattr(daemon_client.app_module, "delete_hermes_session", lambda session_id: True)

    created = daemon_client.client.post(
        "/conversations",
        headers=daemon_client.headers,
        json={"title": "项目 A"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]
    assert created.json()["conversation"]["metadata"]["hermes_session_id"] == conversation_id

    renamed = daemon_client.client.patch(
        f"/conversations/{conversation_id}",
        headers=daemon_client.headers,
        json={"title": "项目 A 改名"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["conversation"]["title"] == "项目 A 改名"

    daemon_client.conversations.create_message(
        conversation_id=conversation_id,
        source="desktop",
        role="user",
        text="会被级联删除",
        emit_event=False,
    )
    archived = daemon_client.client.patch(
        f"/conversations/{conversation_id}",
        headers=daemon_client.headers,
        json={"archived": True},
    )
    assert archived.status_code == 200
    assert archived.json()["conversation"]["metadata"]["archived_at"]

    default_list = daemon_client.client.get("/conversations", headers=daemon_client.headers).json()["conversations"]
    assert conversation_id not in {item["id"] for item in default_list}
    archived_list = daemon_client.client.get(
        "/conversations?include_archived=true",
        headers=daemon_client.headers,
    ).json()["conversations"]
    assert conversation_id in {item["id"] for item in archived_list}

    deleted = daemon_client.client.delete(f"/conversations/{conversation_id}", headers=daemon_client.headers)
    assert deleted.status_code == 200
    assert deleted.json()["hermes_deleted"] is True
    assert daemon_client.conversations.get_conversation(conversation_id) is None
    assert daemon_client.conversations.list_messages(conversation_id) == []


def test_conversation_routes_store_messages_and_replay_events(daemon_client, monkeypatch):
    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        assert message == "你好"
        assert conversation_id == "personal"
        assert kwargs["current_message_id"]
        assert kwargs["exclude_message_ids"] == [kwargs["current_message_id"]]
        return {
            "ok": True,
            "reply": "收到。",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    assert daemon_client.client.get("/conversations").status_code == 403
    conversations = daemon_client.client.get("/conversations", headers=daemon_client.headers)
    assert conversations.status_code == 200
    assert conversations.json()["conversations"][0]["id"] == "personal"

    sent = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )
    assert sent.status_code == 200
    assert sent.json()["ok"] is True
    assert sent.json()["accepted"] is True
    assert sent.json()["turn_id"] == sent.json()["assistant_message"]["id"]
    assert sent.json()["assistant_message"]["status"] == "generating"

    _wait_until(
        lambda: any(
            item["text"] == "收到。" and item["status"] == "sent"
            for item in daemon_client.conversations.list_messages("personal")
        )
    )

    messages = daemon_client.client.get("/conversations/personal/messages", headers=daemon_client.headers)
    assert messages.status_code == 200
    assert [item["text"] for item in messages.json()["messages"]] == ["你好", "收到。"]

    assert daemon_client.client.get("/events/stream").status_code == 403
    events = daemon_client.conversations.list_events_after(0)
    assert any(event["event"] == "message.created" for event in events)
    sse = daemon_client.conversations.format_sse_event(events[-1])
    assert "id:" in sse
    assert "event:" in sse
    assert "data:" in sse


def test_desktop_message_in_weixin_conversation_uses_weixin_turn_context(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    route = {"account_id": "account_a", "chat_id": "wx_contact", "user_id": "wx_contact", "chat_type": "dm"}
    conversation = daemon_client.conversations.create_weixin_conversation(route, title="微信私聊", paths=paths)
    conversation_id = conversation["id"]
    expected_key = daemon_client.turn_coalescer.key_for_weixin(route, conversation_id)
    daemon_client.turn_coalescer.TEXT_BATCH_DELAY_SECONDS = 0.02
    seen: dict[str, object] = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen["message"] = message
        seen["conversation_id"] = conversation_id
        seen["route"] = kwargs.get("route")
        return {
            "ok": True,
            "reply": "微信上下文回复。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    sent = daemon_client.client.post(
        f"/conversations/{conversation_id}/messages",
        headers=daemon_client.headers,
        json={"message": "桌面插一句"},
    )

    assert sent.status_code == 200
    body = sent.json()
    assert body["accepted"] is True
    assert body["assistant_message"]["source"] == "weixin"
    assert body["assistant_message"]["metadata"]["batch_key"] == expected_key
    _wait_until(lambda: seen.get("route") == route)
    assert seen["message"] == "桌面插一句"
    assert seen["conversation_id"] == conversation_id


def test_desktop_slow_reply_returns_accepted_before_agent_finishes(daemon_client, monkeypatch):
    daemon_client.turn_coalescer.TEXT_BATCH_DELAY_SECONDS = 0.2

    async def fail_mode_router(text, paths):
        raise AssertionError("plain chat should not call the mode router before acceptance")

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        await asyncio.sleep(0.2)
        return {
            "ok": True,
            "reply": "慢回复完成。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", fail_mode_router)
    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    started = time.time()
    response = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "调试这个报错"},
    )
    elapsed = time.time() - started

    assert response.status_code == 200
    assert elapsed < 0.15
    body = response.json()
    assert body["accepted"] is True
    assert body["assistant_message"]["status"] == "generating"
    assert body["assistant_message"]["text"] == "正在回复..."
    _wait_until(
        lambda: any(
            item["text"] == "慢回复完成。" and item["status"] == "sent"
            for item in daemon_client.conversations.list_messages("personal")
        ),
        timeout=3.0,
    )


def test_desktop_short_messages_coalesce_into_one_agent_turn(daemon_client, monkeypatch):
    daemon_client.turn_coalescer.TEXT_BATCH_DELAY_SECONDS = 0.2
    seen_prompts = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_prompts.append(message)
        return {
            "ok": True,
            "reply": "合并回复。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    responses = [
        daemon_client.client.post(
            "/conversations/personal/messages",
            headers=daemon_client.headers,
            json={"message": text},
        ).json()
        for text in ["第一条", "第二条", "第三条"]
    ]

    assert all(item["accepted"] is True for item in responses)
    assert len({item["assistant_message"]["id"] for item in responses}) == 1
    _wait_until(lambda: len(seen_prompts) == 1)
    assert "1. 第一条" in seen_prompts[0]
    assert "2. 第二条" in seen_prompts[0]
    assert "3. 第三条" in seen_prompts[0]

    messages = daemon_client.conversations.list_messages("personal")
    assert [item["text"] for item in messages if item["role"] == "user"] == ["第一条", "第二条", "第三条"]
    assistant_messages = [item for item in messages if item["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["text"] == "合并回复。"


def test_desktop_running_turn_queues_next_batch_without_parallel_session(daemon_client, monkeypatch):
    prompts = []
    active = 0
    max_active = 0

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        prompts.append(message)
        if "第一批" in message:
            await asyncio.sleep(0.05)
        active -= 1
        return {
            "ok": True,
            "reply": f"回复 {len(prompts)}",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    first = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "第一批"},
    )
    assert first.status_code == 200
    time.sleep(0.03)
    second = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "第二批"},
    )
    assert second.status_code == 200

    _wait_until(lambda: len(prompts) == 2)
    assert max_active == 1
    assert prompts == ["第一批", "第二批"]


def test_weixin_media_event_registers_attachment_summary_and_ai_prompt(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    cache_dir = paths.hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_file = cache_dir / "note.txt"
    source_file.write_text("第一行\n第二行", encoding="utf-8")
    seen_prompt = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_prompt["message"] = message
        return {
            "ok": True,
            "reply": "我读到了附件。",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="帮我看看这个文件",
                media_urls=[str(source_file)],
                media_types=["text/plain"],
                message_id="weixin_unit_file",
            ),
            paths,
        )
    )

    assert result["ok"] is True
    assert "附件处理结果" in seen_prompt["message"]
    assert "第一行" in seen_prompt["message"]

    messages = daemon_client.client.get("/conversations/personal/messages", headers=daemon_client.headers).json()["messages"]
    user_message = next(item for item in messages if item["role"] == "user")
    assert user_message["attachments"][0]["summary_status"] == "ready"
    assert user_message["attachments"][0]["summary_text"]
    assert "safe_path" not in user_message["attachments"][0]

    event_names = [event["event"] for event in daemon_client.conversations.list_events_after(0)]
    assert "attachment_registered" in event_names
    assert "attachment_summary_updated" in event_names


def test_weixin_same_contact_uses_active_thread_and_can_start_new_thread(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": f"回复 {message}",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    source = SimpleNamespace(chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第一句", media_urls=[], media_types=[], message_id="wx1", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第二句", media_urls=[], media_types=[], message_id="wx2", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert len(seen_conversations) == 2
    assert seen_conversations[0] == seen_conversations[1]
    first_thread = seen_conversations[0]

    created = daemon_client.client.post(
        "/conversations",
        headers=daemon_client.headers,
        json={
            "kind": "weixin",
            "title": "同联系人新线程",
            "metadata": {"weixin_route": {"chat_id": "wx_contact", "user_id": "wx_contact", "chat_type": "dm"}},
        },
    )
    assert created.status_code == 200
    second_thread = created.json()["conversation"]["id"]
    assert second_thread != first_thread
    assert created.json()["conversation"]["metadata"]["weixin_route_active"] is True

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第三句", media_urls=[], media_types=[], message_id="wx3", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert seen_conversations[-1] == second_thread
    first = daemon_client.conversations.get_conversation(first_thread)
    assert first["metadata"]["weixin_route_active"] is False

    reactivated = daemon_client.client.patch(
        f"/conversations/{first_thread}",
        headers=daemon_client.headers,
        json={"weixin_route_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["conversation"]["metadata"]["weixin_route_active"] is True

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第四句", media_urls=[], media_types=[], message_id="wx4", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert seen_conversations[-1] == first_thread
    second = daemon_client.conversations.get_conversation(second_thread)
    assert second["metadata"]["weixin_route_active"] is False


def test_desktop_new_conversation_does_not_steal_weixin_route(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    source = SimpleNamespace(chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="微信第一句", media_urls=[], media_types=[], message_id="wx_route_1", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )
    weixin_thread = seen_conversations[-1]

    desktop = daemon_client.client.post(
        "/conversations",
        headers=daemon_client.headers,
        json={"title": "桌面新对话"},
    )
    assert desktop.status_code == 200
    assert desktop.json()["conversation"]["kind"] == "desktop"
    assert "weixin_route" not in desktop.json()["conversation"]["metadata"]

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="微信第二句", media_urls=[], media_types=[], message_id="wx_route_2", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert seen_conversations[-1] == weixin_thread


def test_weixin_route_key_isolates_multiple_accounts(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    source_a = SimpleNamespace(account_id="account_a", chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    source_b = SimpleNamespace(account_id="account_b", chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="A 账号", media_urls=[], media_types=[], message_id="wx_account_a", source=source_a),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="B 账号", media_urls=[], media_types=[], message_id="wx_account_b", source=source_b),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert len(seen_conversations) == 2
    assert seen_conversations[0] != seen_conversations[1]
    first = daemon_client.conversations.get_conversation(seen_conversations[0])
    second = daemon_client.conversations.get_conversation(seen_conversations[1])
    assert first["metadata"]["weixin_route_key"] == "account_a:dm:wx_contact"
    assert second["metadata"]["weixin_route_key"] == "account_b:dm:wx_contact"
    assert first["metadata"]["weixin_route"]["account_id"] == "account_a"
    assert second["metadata"]["weixin_route"]["account_id"] == "account_b"


def test_desktop_activate_legacy_weixin_route_promotes_account_route(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    paths = daemon_client.config_paths.get_runtime_paths()
    account_source = SimpleNamespace(account_id="account_a", chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="账号 route 旧对话", media_urls=[], media_types=[], message_id="wx_account_route", source=account_source),
            paths,
        )
    )
    account_thread = seen_conversations[-1]

    legacy = daemon_client.conversations.create_conversation(
        title="旧版无账号微信对话",
        kind="weixin",
        metadata={
            "weixin_route": {"chat_id": "wx_contact", "user_id": "wx_contact", "chat_type": "dm"},
            "weixin_route_key": "dm:wx_contact",
            "weixin_route_active": False,
        },
        paths=paths,
    )

    activated = daemon_client.client.patch(
        f"/conversations/{legacy['id']}",
        headers=daemon_client.headers,
        json={"weixin_route_active": True},
    )
    assert activated.status_code == 200
    activated_metadata = activated.json()["conversation"]["metadata"]
    assert activated_metadata["weixin_route_key"] == "account_a:dm:wx_contact"
    assert activated_metadata["weixin_route"]["account_id"] == "account_a"
    assert daemon_client.conversations.get_conversation(account_thread, paths)["metadata"]["weixin_route_active"] is False

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="应该进入刚激活的旧版对话", media_urls=[], media_types=[], message_id="wx_after_activate", source=account_source),
            paths,
        )
    )
    assert seen_conversations[-1] == legacy["id"]


def test_weixin_inbound_repairs_preexisting_legacy_active_route(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    paths = daemon_client.config_paths.get_runtime_paths()
    account_source = SimpleNamespace(account_id="account_a", chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="账号 route 初始对话", media_urls=[], media_types=[], message_id="wx_preexisting_account", source=account_source),
            paths,
        )
    )
    account_thread = seen_conversations[-1]

    legacy = daemon_client.conversations.create_conversation(
        title="已经被旧代码激活的无账号对话",
        kind="weixin",
        metadata={
            "weixin_route": {"chat_id": "wx_contact", "user_id": "wx_contact", "chat_type": "dm"},
            "weixin_route_key": "dm:wx_contact",
            "weixin_route_active": True,
        },
        paths=paths,
    )

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="修复坏状态后的第一句", media_urls=[], media_types=[], message_id="wx_preexisting_repair", source=account_source),
            paths,
        )
    )

    assert seen_conversations[-1] == legacy["id"]
    repaired = daemon_client.conversations.get_conversation(legacy["id"], paths)
    assert repaired["metadata"]["weixin_route_key"] == "account_a:dm:wx_contact"
    assert repaired["metadata"]["weixin_route"]["account_id"] == "account_a"
    assert daemon_client.conversations.get_conversation(account_thread, paths)["metadata"]["weixin_route_active"] is False


def test_desktop_activate_non_weixin_conversation_is_rejected(daemon_client):
    desktop = daemon_client.client.post(
        "/conversations",
        headers=daemon_client.headers,
        json={"title": "普通桌面对话"},
    )
    assert desktop.status_code == 200
    conversation_id = desktop.json()["conversation"]["id"]

    activated = daemon_client.client.patch(
        f"/conversations/{conversation_id}",
        headers=daemon_client.headers,
        json={"weixin_route_active": True},
    )

    assert activated.status_code == 404
    assert activated.json()["detail"] == "没有找到这个对话。"
    stored = daemon_client.conversations.get_conversation(conversation_id)
    assert "weixin_route_active" not in stored["metadata"]


def test_legacy_route_with_multiple_accounts_waits_for_real_inbound_account(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    paths = daemon_client.config_paths.get_runtime_paths()
    source_a = SimpleNamespace(account_id="account_a", chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    source_b = SimpleNamespace(account_id="account_b", chat_id="wx_contact", user_id="wx_contact", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="账号 A 初始消息", media_urls=[], media_types=[], message_id="wx_multi_a_1", source=source_a),
            paths,
        )
    )
    account_a_thread = seen_conversations[-1]
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="账号 B 初始消息", media_urls=[], media_types=[], message_id="wx_multi_b_1", source=source_b),
            paths,
        )
    )
    account_b_thread = seen_conversations[-1]

    legacy = daemon_client.conversations.create_conversation(
        title="旧版无账号微信对话",
        kind="weixin",
        metadata={
            "weixin_route": {"chat_id": "wx_contact", "user_id": "wx_contact", "chat_type": "dm"},
            "weixin_route_key": "dm:wx_contact",
            "weixin_route_active": False,
        },
        paths=paths,
    )

    activated = daemon_client.client.patch(
        f"/conversations/{legacy['id']}",
        headers=daemon_client.headers,
        json={"weixin_route_active": True},
    )
    assert activated.status_code == 200
    activated_metadata = activated.json()["conversation"]["metadata"]
    assert activated_metadata["weixin_route_key"] == "dm:wx_contact"
    assert "account_id" not in activated_metadata["weixin_route"]
    assert daemon_client.conversations.get_conversation(account_a_thread, paths)["metadata"]["weixin_route_active"] is True
    assert daemon_client.conversations.get_conversation(account_b_thread, paths)["metadata"]["weixin_route_active"] is True

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="账号 A 选择旧版对话", media_urls=[], media_types=[], message_id="wx_multi_a_2", source=source_a),
            paths,
        )
    )
    assert seen_conversations[-1] == legacy["id"]
    repaired = daemon_client.conversations.get_conversation(legacy["id"], paths)
    assert repaired["metadata"]["weixin_route_key"] == "account_a:dm:wx_contact"
    assert repaired["metadata"]["weixin_route"]["account_id"] == "account_a"
    assert daemon_client.conversations.get_conversation(account_a_thread, paths)["metadata"]["weixin_route_active"] is False
    assert daemon_client.conversations.get_conversation(account_b_thread, paths)["metadata"]["weixin_route_active"] is True

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="账号 B 仍进账号 B 对话", media_urls=[], media_types=[], message_id="wx_multi_b_2", source=source_b),
            paths,
        )
    )
    assert seen_conversations[-1] == account_b_thread


def test_weixin_switch_invalid_number_keeps_current_conversation(daemon_client, monkeypatch):
    seen_chats = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_chats.append((message, conversation_id))
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    paths = daemon_client.config_paths.get_runtime_paths()
    source = SimpleNamespace(chat_id="wx_bad_number", user_id="wx_bad_number", chat_type="dm")
    first = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第一句普通聊天", media_urls=[], media_types=[], message_id="wx_bad_number_1", source=source),
            paths,
        )
    )
    first_conversation = first["chat"]["conversation_id"]
    second = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="新开一个对话", media_urls=[], media_types=[], message_id="wx_bad_number_new", source=source),
            paths,
        )
    )
    second_conversation = second["conversation"]["id"]

    menu = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="切换对话", media_urls=[], media_types=[], message_id="wx_bad_number_menu", source=source),
            paths,
        )
    )
    assert "最近的微信对话" in menu["message"]
    invalid = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="9", media_urls=[], media_types=[], message_id="wx_bad_number_invalid", source=source),
            paths,
        )
    )

    assert invalid["intent"]["kind"] == "conversation_switch_error"
    assert "没有这个编号" in invalid["message"]
    active = daemon_client.conversations.active_weixin_conversation(
        {"chat_id": "wx_bad_number", "user_id": "wx_bad_number", "chat_type": "dm"},
        paths=paths,
    )
    assert active["id"] == second_conversation
    assert first_conversation != second_conversation
    assert [item[0] for item in seen_chats] == ["第一句普通聊天"]


def test_deleted_active_weixin_conversation_next_inbound_creates_new_thread(daemon_client, monkeypatch):
    seen_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_conversations.append(conversation_id)
        return {
            "ok": True,
            "reply": "微信回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    paths = daemon_client.config_paths.get_runtime_paths()
    source = SimpleNamespace(chat_id="wx_delete_active", user_id="wx_delete_active", chat_type="dm")
    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第一句", media_urls=[], media_types=[], message_id="wx_delete_active_1", source=source),
            paths,
        )
    )
    deleted_id = seen_conversations[-1]
    assert daemon_client.conversations.delete_conversation(deleted_id, paths=paths) is not None

    asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="删除后再来", media_urls=[], media_types=[], message_id="wx_delete_active_2", source=source),
            paths,
        )
    )

    assert seen_conversations[-1] != deleted_id
    assert daemon_client.conversations.get_conversation(deleted_id, paths) is None
    created = daemon_client.conversations.get_conversation(seen_conversations[-1], paths)
    assert created["kind"] == "weixin"
    assert created["metadata"]["weixin_route_active"] is True


def test_weixin_inbound_reply_uses_generating_placeholder_and_update(daemon_client, monkeypatch):
    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        assert kwargs["require_existing_conversation"] is True
        assert kwargs["exclude_message_ids"]
        return {
            "ok": True,
            "reply": "占位已更新。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    source = SimpleNamespace(chat_id="wx_placeholder", user_id="wx_placeholder", chat_type="dm")
    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="看看占位", media_urls=[], media_types=[], message_id="wx_placeholder_1", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert result["ok"] is True
    events = daemon_client.conversations.list_events_after(0)
    assistant_created = [
        event
        for event in events
        if event["event"] == "message.created"
        and (event["data"].get("message") or {}).get("role") == "assistant"
    ]
    assistant_updated = [event for event in events if event["event"] == "message.updated"]
    assert assistant_created
    assert assistant_created[-1]["data"]["message"]["status"] == "generating"
    assert assistant_updated
    assert assistant_updated[-1]["data"]["message"]["id"] == assistant_created[-1]["data"]["message"]["id"]
    assert assistant_updated[-1]["data"]["message"]["status"] == "sent"
    assert assistant_updated[-1]["data"]["message"]["text"] == "占位已更新。"


def test_weixin_same_route_short_texts_coalesce_into_one_reply(daemon_client, monkeypatch):
    daemon_client.turn_coalescer.TEXT_BATCH_DELAY_SECONDS = 0.2
    prompts = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        prompts.append(message)
        return {
            "ok": True,
            "reply": "微信合并回复。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    async def run_messages():
        source = SimpleNamespace(chat_id="wx_coalesce", user_id="wx_coalesce", chat_type="dm")
        tasks = [
            asyncio.create_task(
                gateway.handle_weixin_message_event(
                    SimpleNamespace(text=text, media_urls=[], media_types=[], message_id=f"wx_coalesce_{index}", source=source),
                    daemon_client.config_paths.get_runtime_paths(),
                )
            )
            for index, text in enumerate(["第一条", "第二条", "第三条"], start=1)
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_messages())

    assert len(prompts) == 1
    assert "1. 第一条" in prompts[0]
    assert "2. 第二条" in prompts[0]
    assert "3. 第三条" in prompts[0]
    assert sum(1 for item in results if item.get("chat", {}).get("reply") == "微信合并回复。") == 1
    assert sum(1 for item in results if item.get("suppressed")) == 2
    conversation_id = next(item["chat"]["conversation_id"] for item in results if item.get("chat"))
    messages = daemon_client.conversations.list_messages(conversation_id)
    assert len([item for item in messages if item["role"] == "assistant"]) == 1


def test_weixin_inbound_deleted_conversation_does_not_resurrect_or_reply(daemon_client, monkeypatch):
    deleted_conversations = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        deleted_conversations.append(conversation_id)
        daemon_client.conversations.delete_conversation(conversation_id, paths=paths)
        return {
            "ok": True,
            "reply": "这条回复不应该发送。",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    source = SimpleNamespace(chat_id="wx_delete", user_id="wx_delete", chat_type="dm")
    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="删除竞态", media_urls=[], media_types=[], message_id="wx_delete_1", source=source),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert result["suppressed"] is True
    assert deleted_conversations
    assert daemon_client.conversations.get_conversation(deleted_conversations[0]) is None
    assert daemon_client.conversations.list_messages(deleted_conversations[0]) == []
    events = daemon_client.conversations.list_events_after(0)
    assert not [
        event
        for event in events
        if event["event"] == "message.updated"
        and (event["data"].get("message") or {}).get("text") == "这条回复不应该发送。"
    ]


def test_weixin_natural_language_conversation_switching_stays_on_same_route(daemon_client, monkeypatch):
    seen_chats = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_chats.append((message, conversation_id))
        return {
            "ok": True,
            "reply": f"回复 {message}",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    paths = daemon_client.config_paths.get_runtime_paths()
    source = SimpleNamespace(chat_id="wx_switch", user_id="wx_switch", chat_type="dm")
    other_route = {"chat_id": "wx_other", "user_id": "wx_other", "chat_type": "dm"}
    daemon_client.conversations.create_weixin_conversation(other_route, title="其他联系人", paths=paths)

    first = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="第一句普通聊天", media_urls=[], media_types=[], message_id="wx_switch_1", source=source),
            paths,
        )
    )
    first_conversation = first["chat"]["conversation_id"]

    created = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="新开一个对话", media_urls=[], media_types=[], message_id="wx_switch_new", source=source),
            paths,
        )
    )
    second_conversation = created["conversation"]["id"]
    assert second_conversation != first_conversation
    assert daemon_client.conversations.active_weixin_conversation(
        {"chat_id": "wx_switch", "user_id": "wx_switch", "chat_type": "dm"},
        paths=paths,
    )["id"] == second_conversation

    previous = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="切回上一个对话", media_urls=[], media_types=[], message_id="wx_switch_prev", source=source),
            paths,
        )
    )
    assert previous["conversation"]["id"] == first_conversation

    menu = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="切换对话", media_urls=[], media_types=[], message_id="wx_switch_menu", source=source),
            paths,
        )
    )
    assert "最近的微信对话" in menu["message"]
    assert "其他联系人" not in menu["message"]
    selected = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(text="2", media_urls=[], media_types=[], message_id="wx_switch_select", source=source),
            paths,
        )
    )
    assert selected["conversation"]["id"] == second_conversation
    assert [item[0] for item in seen_chats] == ["第一句普通聊天"]


def _write_unit_png(path):
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax5kNQAAAAASUVORK5CYII="
        )
    )


def test_weixin_image_preview_only_does_not_claim_visual_read(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    cache_dir = paths.hermes_home / "cache" / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    image_file = cache_dir / "photo.png"
    _write_unit_png(image_file)
    seen_prompt = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_prompt["message"] = message
        return {
            "ok": True,
            "reply": "我会按未识别处理。",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    async def fake_describe_image_data_url(*args, **kwargs):
        return {
            "ok": False,
            "error_code": "image_not_supported",
            "backend": "none",
            "stage": "capability.unsupported",
            "message": "图片已收到并可预览；当前 DeepSeek 文本模型 deepseek-chat 不能识别图片内容。",
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.chat_client, "describe_image_data_url", fake_describe_image_data_url)

    import lilsunspot.daemon.gateway as gateway

    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="这张图里有什么",
                media_urls=[str(image_file)],
                media_types=["image/png"],
                message_id="weixin_unit_image",
            ),
            paths,
        )
    )

    assert result["ok"] is True
    assert "附件处理结果" in seen_prompt["message"]
    assert "不能识别图片内容" in seen_prompt["message"]

    messages = daemon_client.client.get("/conversations/personal/messages", headers=daemon_client.headers).json()["messages"]
    user_message = next(item for item in messages if item["role"] == "user")
    attachment = user_message["attachments"][0]
    assert attachment["summary_status"] == "preview_only"
    assert attachment["summary_text"] == ""
    assert attachment["preview_data_url"].startswith("data:image/png;base64,")
    assert "不能识别图片内容" in attachment["reason_cn"]
    assert attachment["metadata"]["recognition_backend"] == "none"
    assert attachment["metadata"]["recognition_stage"] == "capability.unsupported"
    assert attachment["metadata"]["recognition_error_code"] == "image_not_supported"


def test_weixin_image_visual_summary_marks_attachment_recognized(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    cache_dir = paths.hermes_home / "cache" / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    image_file = cache_dir / "receipt.png"
    _write_unit_png(image_file)

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        return {
            "ok": True,
            "reply": "已按图片识别结果回复。",
            "engine": "hermes_agent_loop",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    async def fake_describe_image_data_url(*args, **kwargs):
        return {
            "ok": True,
            "summary": "画面里是一张收据。",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "backend": "auxiliary_vision",
            "stage": "vision.auxiliary",
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.chat_client, "describe_image_data_url", fake_describe_image_data_url)

    import lilsunspot.daemon.gateway as gateway

    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="帮我看图",
                media_urls=[str(image_file)],
                media_types=["image/png"],
                message_id="weixin_unit_image_vision",
            ),
            paths,
        )
    )

    assert result["ok"] is True
    messages = daemon_client.client.get("/conversations/personal/messages", headers=daemon_client.headers).json()["messages"]
    user_message = next(item for item in messages if item["role"] == "user")
    attachment = user_message["attachments"][0]
    assert attachment["summary_status"] == "recognized"
    assert attachment["summary_text"] == "画面里是一张收据。"
    assert attachment["reason_cn"] == ""
    assert attachment["metadata"]["recognition_backend"] == "auxiliary_vision"
    assert attachment["metadata"]["recognition_stage"] == "vision.auxiliary"
    assert attachment["metadata"]["recognition_error_code"] == ""


def test_desktop_message_uploads_image_attachment_and_adds_summary_to_prompt(daemon_client, monkeypatch):
    seen_prompt = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_prompt["message"] = message
        seen_prompt["current_message_id"] = kwargs.get("current_message_id")
        return {
            "ok": True,
            "reply": "已收到图片。",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    async def fake_describe_image_data_url(*args, **kwargs):
        return {
            "ok": False,
            "error_code": "image_not_supported",
            "backend": "none",
            "stage": "capability.unsupported",
            "message": "图片已收到并可预览；当前模型不能识别图片内容。",
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.app_module, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.chat_client, "describe_image_data_url", fake_describe_image_data_url)
    image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax5kNQAAAAASUVORK5CYII="

    response = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={
            "message": "请看这张图",
            "attachments": [
                {
                    "file_name": "desk.png",
                    "mime_type": "image/png",
                    "data_base64": image_base64,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["accepted"] is False
    assert seen_prompt["current_message_id"] == body["user_message"]["id"]
    assert "附件处理结果" in seen_prompt["message"]
    assert "当前模型不能识别图片内容" in seen_prompt["message"]

    attachment = body["user_message"]["attachments"][0]
    assert attachment["file_name"] == "desk.png"
    assert attachment["summary_status"] == "preview_only"
    assert attachment["preview_data_url"].startswith("data:image/png;base64,")
    assert "safe_path" not in attachment
    assert attachment["metadata"]["recognition_backend"] == "none"
    assert attachment["metadata"]["recognition_stage"] == "capability.unsupported"
    assert attachment["metadata"]["recognition_error_code"] == "image_not_supported"


def test_desktop_attachment_return_uses_assistant_attachment_card(daemon_client, monkeypatch):
    seen_prompt = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_prompt["message"] = message
        match = re.search(r"MEDIA:lilsunspot-attachment://att_[A-Za-z0-9_-]+", message)
        assert match is not None
        return {
            "ok": True,
            "reply": f"给你。\n{match.group(0)}",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    async def fake_describe_image_data_url(*args, **kwargs):
        return {
            "ok": False,
            "error_code": "image_not_supported",
            "backend": "none",
            "stage": "capability.unsupported",
            "message": "图片已收到并可预览；当前模型不能识别图片内容。",
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.app_module, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.chat_client, "describe_image_data_url", fake_describe_image_data_url)
    image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ax5kNQAAAAASUVORK5CYII="

    response = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={
            "message": "把这张图再发给我",
            "attachments": [
                {
                    "file_name": "desk.png",
                    "mime_type": "image/png",
                    "data_base64": image_base64,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "返还标记" in seen_prompt["message"]
    assert body["assistant_message"]["text"] == "给你。"
    assert "MEDIA:" not in body["assistant_message"]["text"]
    assert body["assistant_message"]["metadata"]["delivery"]["status"] == "delivered"
    assert body["assistant_message"]["metadata"]["delivery"]["delivered_count"] == 1
    returned = body["assistant_message"]["attachments"][0]
    assert returned["file_name"] == "desk.png"
    assert returned["summary_status"] == "preview_only"
    assert "safe_path" not in returned


def test_media_delivery_rejects_cross_conversation_attachment(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation_a = daemon_client.conversations.create_conversation(title="A", paths=paths)
    conversation_b = daemon_client.conversations.create_conversation(title="B", paths=paths)
    source_message = daemon_client.conversations.create_message(
        conversation_id=conversation_a["id"],
        source="desktop",
        role="user",
        text="上传 A 文件",
        paths=paths,
    )
    attachment = daemon_client.attachments.register_uploaded_attachments(
        message_id=source_message["id"],
        conversation_id=conversation_a["id"],
        files=[{"file_name": "a.txt", "mime_type": "text/plain", "data": b"hello"}],
        paths=paths,
    )[0]

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        return {
            "ok": True,
            "reply": f"MEDIA:lilsunspot-attachment://{attachment['id']}",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    monkeypatch.setattr(daemon_client.app_module, "send_agent_message", fake_send_agent_message)

    response = daemon_client.client.post(
        f"/conversations/{conversation_b['id']}/messages",
        headers=daemon_client.headers,
        json={
            "message": "返还别的对话文件",
            "attachments": [{"file_name": "b.txt", "mime_type": "text/plain", "data_base64": base64.b64encode(b"b").decode("ascii")}],
        },
    )

    assert response.status_code == 200
    assistant = response.json()["assistant_message"]
    assert assistant["attachments"] == []
    assert "MEDIA:" not in assistant["text"]
    assert assistant["metadata"]["delivery"]["status"] == "rejected"
    assert assistant["metadata"]["delivery"]["reason_code"] == "cross_conversation"


def test_desktop_invalid_upload_does_not_create_message(daemon_client):
    response = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={
            "message": "坏附件",
            "attachments": [{"file_name": "broken.png", "mime_type": "image/png", "data_base64": "not base64"}],
        },
    )

    assert response.status_code == 400
    messages = daemon_client.client.get("/conversations/personal/messages", headers=daemon_client.headers).json()["messages"]
    assert messages == []


def test_attachment_source_rejects_credential_dir_and_csv_uses_structured_summary(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    account_dir = paths.hermes_home / "weixin" / "accounts"
    account_dir.mkdir(parents=True, exist_ok=True)
    credential_file = account_dir / "account.json"
    credential_file.write_text('{"token":"secret"}', encoding="utf-8")

    try:
        daemon_client.attachments.assert_safe_attachment_path(credential_file, paths)
    except daemon_client.attachments.AttachmentError as exc:
        assert "安全缓存目录" in str(exc)
    else:
        raise AssertionError("credential directory must not be accepted as an attachment source")

    cache_dir = paths.hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_file = cache_dir / "table.csv"
    csv_file.write_text("name,score\n小黑子,100\n", encoding="utf-8")
    user_message = daemon_client.conversations.create_message(
        source="weixin",
        role="user",
        text="表格",
        emit_event=False,
        paths=paths,
    )
    attachment = daemon_client.attachments.register_message_attachments(
        message_id=user_message["id"],
        conversation_id="personal",
        media_urls=[str(csv_file)],
        media_types=["text/plain"],
        paths=paths,
    )[0]

    assert attachment["summary_status"] == "ready"
    assert "列名：name、score" in attachment["summary_text"]
    assert "前 20 行" in attachment["summary_text"]


def test_natural_language_mode_intents_and_long_task_guard(daemon_client, monkeypatch):
    async def fake_route(text, paths):
        if text == "切到务实一点":
            return daemon_client.mode_intents.ModeIntent(kind="mode", mode="pragmatic")
        if text == "现在是什么风格":
            return daemon_client.mode_intents.ModeIntent(kind="query")
        return None

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", fake_route)

    pragmatic = daemon_client.client.post(
        "/gateway/weixin/commands/handle",
        headers=daemon_client.headers,
        json={"text": "切到务实一点"},
    )
    assert pragmatic.status_code == 200
    assert pragmatic.json()["ok"] is True
    assert pragmatic.json()["mode"]["current"] == "pragmatic"
    assert "务实" in pragmatic.json()["message"]

    query = daemon_client.client.post(
        "/gateway/weixin/commands/handle",
        headers=daemon_client.headers,
        json={"text": "现在是什么风格"},
    )
    assert query.status_code == 200
    assert "表达" in query.json()["message"]

    long_task = daemon_client.client.post(
        "/gateway/weixin/commands/handle",
        headers=daemon_client.headers,
        json={"text": "详细解释一下这个合同"},
    )
    assert long_task.status_code == 200
    current = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()
    assert current["current"] == "pragmatic"


def test_weixin_semantic_mode_router_switches_emotional_and_emits_event(daemon_client, monkeypatch):
    async def fake_route(text, paths):
        assert text == "切换到感性模式"
        return daemon_client.mode_intents.ModeIntent(kind="mode", mode="emotional")

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", fake_route)

    result = daemon_client.client.post(
        "/gateway/weixin/commands/handle",
        headers=daemon_client.headers,
        json={"text": "切换到感性模式"},
    )

    assert result.status_code == 200
    assert result.json()["ok"] is True
    assert result.json()["mode"]["current"] == "emotional"
    current = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()
    assert current["current"] == "emotional"
    events = daemon_client.conversations.list_events_after(0)
    assert any(event["event"] == "mode.changed" for event in events)


def test_semantic_mode_switch_uses_target_profile_default_sliders(daemon_client, monkeypatch):
    selected = daemon_client.client.post(
        "/modes/select",
        headers=daemon_client.headers,
        json={"mode": "emotional", "style_axis": 80, "detail_level": 65, "autonomy_level": 45},
    )
    assert selected.status_code == 200

    async def fake_route(text, paths):
        assert text == "切到均衡模式"
        return daemon_client.mode_intents.ModeIntent(kind="mode", mode="balanced")

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", fake_route)

    result = daemon_client.client.post(
        "/gateway/weixin/commands/handle",
        headers=daemon_client.headers,
        json={"text": "切到均衡模式"},
    )

    assert result.status_code == 200
    mode = result.json()["mode"]
    assert mode["current"] == "balanced"
    assert mode["profile"]["style_axis"] == 45
    assert mode["profile"]["detail_level"] == 60
    assert mode["profile"]["autonomy_level"] == 60
    current = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()
    assert current["profile"]["style_axis"] == 45
    assert current["profile"]["detail_level"] == 60
    assert current["profile"]["autonomy_level"] == 60


def test_semantic_slider_adjustment_saves_custom_mode(daemon_client, monkeypatch):
    selected = daemon_client.client.post(
        "/modes/select",
        headers=daemon_client.headers,
        json={"mode": "balanced"},
    )
    assert selected.status_code == 200

    async def fake_route(text, paths):
        assert text == "回答再详细一点"
        return daemon_client.mode_intents.ModeIntent(kind="slider", slider="detail_level", delta=20)

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", fake_route)

    result = daemon_client.client.post(
        "/gateway/weixin/commands/handle",
        headers=daemon_client.headers,
        json={"text": "回答再详细一点"},
    )

    assert result.status_code == 200
    mode = result.json()["mode"]
    assert mode["current"] == "custom"
    assert mode["profile"]["style_axis"] == 45
    assert mode["profile"]["detail_level"] == 80
    assert mode["profile"]["autonomy_level"] == 60
    current = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()
    assert current["current"] == "custom"


def test_desktop_semantic_mode_router_switches_mode_without_chat_reply(daemon_client, monkeypatch):
    async def fake_route(text, paths):
        assert text == "模式切换到感性"
        return daemon_client.mode_intents.ModeIntent(kind="mode", mode="emotional")

    async def fail_chat(*args, **kwargs):
        raise AssertionError("mode routing should not fall through to normal chat")

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", fake_route)
    monkeypatch.setattr(daemon_client.app_module, "send_agent_message", fail_chat)
    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fail_chat)

    result = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "模式切换到感性"},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is True
    assert "已把回答风格调成" in body["assistant_message"]["text"]
    assert body["chat"]["mode_intent"]["kind"] == "mode"
    assert body["chat"]["mode"]["current"] == "emotional"
    current = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()
    assert current["current"] == "emotional"


def test_semantic_mode_router_ignores_normal_task_and_invalid_model_output(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()

    async def invalid_router_reply(text, paths):
        return "我觉得应该切换。"

    monkeypatch.setattr(daemon_client.mode_intents, "_call_mode_router_model", invalid_router_reply)
    invalid = asyncio.run(daemon_client.mode_intents._route_mode_intent_with_model("切换到感性模式", paths))
    assert invalid is None

    async def chat_route(text, paths):
        assert text == "帮我写一个感性的文案"
        return None

    seen_chat = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_chat["message"] = message
        return {
            "ok": True,
            "reply": "文案草稿。",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.mode_intents, "_route_mode_intent_with_model", chat_route)
    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    result = daemon_client.client.post(
        "/conversations/personal/messages",
        headers=daemon_client.headers,
        json={"message": "帮我写一个感性的文案"},
    )

    assert result.status_code == 200
    assert result.json()["accepted"] is True
    assert result.json()["assistant_message"]["status"] == "generating"
    _wait_until(lambda: seen_chat.get("message") == "帮我写一个感性的文案")
    _wait_until(
        lambda: any(
            item["text"] == "文案草稿。" and item["status"] == "sent"
            for item in daemon_client.conversations.list_messages("personal")
        )
    )
    current = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()
    assert current["current"] == "balanced"


def test_runtime_text_event_preserves_weixin_message_id(daemon_client):
    reply = asyncio.run(
        daemon_client.weixin_runtime.handle_inbound_weixin_event(
            SimpleNamespace(text="现在是什么风格", media_urls=[], media_types=[], message_id="wx_text_unit")
        )
    )

    assert reply
    messages = daemon_client.client.get("/conversations/personal/messages", headers=daemon_client.headers).json()["messages"]
    user_message = next(item for item in messages if item["role"] == "user" and item["text"] == "现在是什么风格")
    assert user_message["metadata"]["message_id"] == "wx_text_unit"


class FakeSendResult:
    def __init__(self, success=True):
        self.success = success
        self.message_id = "sent_unit"
        self.error = "" if success else "failed"


class FakeWeixinSendAdapter:
    is_connected = True

    def __init__(self):
        self.calls = []

    async def send(self, recipient, message):
        self.calls.append(("send", recipient, message))
        return FakeSendResult()

    async def send_document(self, recipient, path):
        self.calls.append(("document", recipient, path))
        return FakeSendResult()

    async def send_image_file(self, recipient, path):
        self.calls.append(("image", recipient, path))
        return FakeSendResult()


def test_weixin_same_channel_media_reply_uses_official_media_delivery(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    route = {"chat_id": "wx_user", "user_id": "wx_user", "chat_type": "dm"}
    conversation = daemon_client.conversations.create_weixin_conversation(route, title="微信私聊", paths=paths)
    source_message = daemon_client.conversations.create_message(
        conversation_id=conversation["id"],
        source="weixin",
        role="user",
        text="之前的文件",
        paths=paths,
    )
    attachment = daemon_client.attachments.register_uploaded_attachments(
        message_id=source_message["id"],
        conversation_id=conversation["id"],
        files=[{"file_name": "wx.txt", "mime_type": "text/plain", "data": b"hello"}],
        source="weixin",
        paths=paths,
    )[0]
    seen_prompts = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_prompts.append(message)
        return {
            "ok": True,
            "reply": f"好的。\nMEDIA:lilsunspot-attachment://{attachment['id']}",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="把刚才的文件发给我",
                media_urls=[],
                media_types=[],
                message_id="wx_media_return",
                source=SimpleNamespace(chat_id="wx_user", user_id="wx_user", chat_type="dm"),
            ),
            paths,
        )
    )

    assert result["ok"] is True
    assert "返还标记" in seen_prompts[0]
    assert result["chat"]["visible_reply"] == "好的。"
    assert "MEDIA:" in result["chat"]["reply"]
    assert "lilsunspot-attachment://" not in result["chat"]["reply"]
    messages = daemon_client.client.get(f"/conversations/{conversation['id']}/messages", headers=daemon_client.headers).json()["messages"]
    assistant = next(item for item in reversed(messages) if item["role"] == "assistant" and item["status"] == "sent")
    assert assistant["text"] == "好的。"
    assert "MEDIA:" not in assistant["text"]
    assert assistant["metadata"]["delivery"]["status"] == "delivered"
    assert assistant["attachments"][0]["file_name"] == "wx.txt"


def test_weixin_approval_approved_sends_text_and_file_rejected_does_not_send(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    cache_dir = paths.hermes_home / "cache" / "documents"
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_file = cache_dir / "send.txt"
    source_file.write_text("要发送的文件", encoding="utf-8")
    image_dir = paths.hermes_home / "cache" / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_file = image_dir / "send.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\nunit-test-image")
    user_message = daemon_client.conversations.create_message(
        source="weixin",
        role="assistant",
        text="生成文件",
        paths=paths,
    )
    attachment = daemon_client.attachments.register_message_attachments(
        message_id=user_message["id"],
        conversation_id="personal",
        media_urls=[str(source_file)],
        media_types=["text/plain"],
        paths=paths,
    )[0]
    image_attachment = daemon_client.attachments.register_message_attachments(
        message_id=user_message["id"],
        conversation_id="personal",
        media_urls=[str(image_file)],
        media_types=["image/png"],
        paths=paths,
    )[0]

    fake_adapter = FakeWeixinSendAdapter()
    monkeypatch.setattr(daemon_client.weixin_runtime, "_adapter", fake_adapter)

    approval = daemon_client.client.post(
        "/gateway/weixin/send",
        headers=daemon_client.headers,
        json={
            "recipient": "wx_user",
            "message": "看附件",
            "attachment_ids": [attachment["id"], image_attachment["id"]],
        },
    ).json()["approval"]
    approved = daemon_client.client.post(
        f"/safety/approvals/{approval['id']}/decide",
        headers=daemon_client.headers,
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["delivery"]["ok"] is True
    assert fake_adapter.calls[0] == ("send", "wx_user", "看附件")
    assert fake_adapter.calls[1][0] == "document"
    assert fake_adapter.calls[2][0] == "image"

    second = daemon_client.client.post(
        "/gateway/weixin/send",
        headers=daemon_client.headers,
        json={"recipient": "wx_user", "message": "不要发"},
    ).json()["approval"]
    rejected = daemon_client.client.post(
        f"/safety/approvals/{second['id']}/decide",
        headers=daemon_client.headers,
        json={"decision": "rejected"},
    )
    assert rejected.status_code == 200
    assert len(fake_adapter.calls) == 3


def test_weixin_approval_validates_files_before_sending_text(daemon_client, monkeypatch):
    fake_adapter = FakeWeixinSendAdapter()
    monkeypatch.setattr(daemon_client.weixin_runtime, "_adapter", fake_adapter)

    approval = daemon_client.client.post(
        "/gateway/weixin/send",
        headers=daemon_client.headers,
        json={"recipient": "wx_user", "message": "看附件", "attachment_ids": ["att_missing"]},
    ).json()["approval"]
    approved = daemon_client.client.post(
        f"/safety/approvals/{approval['id']}/decide",
        headers=daemon_client.headers,
        json={"decision": "approved"},
    )

    assert approved.status_code == 200
    assert approved.json()["delivery"]["ok"] is False
    assert "附件" in approved.json()["delivery"]["message"]
    assert fake_adapter.calls == []


def test_weixin_approval_rejects_unsafe_attachment_path_before_sending_text(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    outside_file = paths.data_dir.parent / "outside.txt"
    outside_file.write_text("不应直接发送", encoding="utf-8")
    user_message = daemon_client.conversations.create_message(
        source="assistant",
        role="assistant",
        text="生成了一个不安全路径文件",
        paths=paths,
    )
    attachment = daemon_client.conversations.create_attachment_record(
        attachment_id="att_unsafe_unit",
        message_id=user_message["id"],
        conversation_id="personal",
        safe_path=outside_file,
        file_name="outside.txt",
        mime_type="text/plain",
        size_bytes=outside_file.stat().st_size,
        summary_status="ready",
        metadata={"source": "generated"},
        paths=paths,
    )

    fake_adapter = FakeWeixinSendAdapter()
    monkeypatch.setattr(daemon_client.weixin_runtime, "_adapter", fake_adapter)

    approval = daemon_client.client.post(
        "/gateway/weixin/send",
        headers=daemon_client.headers,
        json={"recipient": "wx_user", "message": "看附件", "attachment_ids": [attachment["id"]]},
    ).json()["approval"]
    approved = daemon_client.client.post(
        f"/safety/approvals/{approval['id']}/decide",
        headers=daemon_client.headers,
        json={"decision": "approved"},
    )

    assert approved.status_code == 200
    assert approved.json()["delivery"]["ok"] is False
    assert "附件" in approved.json()["delivery"]["message"]
    assert fake_adapter.calls == []


def test_weixin_approval_does_not_send_when_weixin_is_disconnected(daemon_client, monkeypatch):
    monkeypatch.setattr(daemon_client.weixin_runtime, "_adapter", None)

    approval = daemon_client.client.post(
        "/gateway/weixin/send",
        headers=daemon_client.headers,
        json={"recipient": "wx_user", "message": "只发文本"},
    ).json()["approval"]
    approved = daemon_client.client.post(
        f"/safety/approvals/{approval['id']}/decide",
        headers=daemon_client.headers,
        json={"decision": "approved"},
    )

    assert approved.status_code == 200
    assert approved.json()["delivery"]["ok"] is False
    assert "微信还没有连接" in approved.json()["delivery"]["message"]


def test_weixin_file_request_text_stays_on_normal_chat_path(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    generated_dir = daemon_client.attachments.attachment_storage_root(paths)
    generated_file = generated_dir / "latest.docx"
    generated_file.write_bytes(b"not-a-real-docx")
    attachment = daemon_client.attachments.register_generated_attachment(
        generated_file,
        message_text="已生成 Word 文件。",
        paths=paths,
    )

    fake_adapter = FakeWeixinSendAdapter()
    monkeypatch.setattr(daemon_client.weixin_runtime, "_adapter", fake_adapter)
    seen_messages = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_messages.append(message)
        return {
            "ok": True,
            "reply": "普通聊天回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    import lilsunspot.daemon.gateway as gateway

    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="把这个 Word 发给我",
                media_urls=[],
                media_types=[],
                message_id="wx_file_text_chat",
                source=SimpleNamespace(chat_id="wx_user", user_id="wx_user", chat_type="dm"),
            ),
            paths,
        )
    )

    assert result["ok"] is True
    assert result["intent"]["kind"] == "chat_message"
    assert result["chat"]["reply"] == "普通聊天回复"
    assert seen_messages == ["把这个 Word 发给我"]
    assert daemon_client.client.get("/safety/approvals", headers=daemon_client.headers).json()["pending"] == []
    assert fake_adapter.calls == []

    conversation_id = result["chat"]["conversation_id"]
    messages = daemon_client.client.get(f"/conversations/{conversation_id}/messages", headers=daemon_client.headers).json()["messages"]
    request_message = next(item for item in messages if item["text"] == "把这个 Word 发给我")
    assert request_message["metadata"]["weixin_route"]["chat_id"] == "wx_user"
    assert attachment["id"]


def test_weixin_generate_file_text_stays_on_normal_chat_path(daemon_client, monkeypatch):
    seen_messages = []

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen_messages.append(message)
        return {
            "ok": True,
            "reply": "普通聊天回复",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)
    import lilsunspot.daemon.gateway as gateway

    result = asyncio.run(
        gateway.handle_weixin_message_event(
            SimpleNamespace(
                text="生成一个word文档，内容是hello world，发给我",
                media_urls=[],
                media_types=[],
                message_id="wx_create_send_file",
                source=SimpleNamespace(chat_id="wx_user", user_id="wx_user", chat_type="dm"),
            ),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert result["ok"] is True
    assert result["intent"]["kind"] == "chat_message"
    assert result["chat"]["reply"] == "普通聊天回复"
    assert seen_messages == ["生成一个word文档，内容是hello world，发给我"]
    assert daemon_client.client.get("/safety/approvals", headers=daemon_client.headers).json()["pending"] == []
