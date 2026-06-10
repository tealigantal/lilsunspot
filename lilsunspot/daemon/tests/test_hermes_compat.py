from __future__ import annotations

import asyncio
from types import SimpleNamespace


def test_hermes_compatibility_report_covers_official_interfaces(daemon_client):
    report = daemon_client.hermes_compat.audit_hermes_compatibility()

    assert report["ok"] is True
    assert report["upstream_commit"]
    assert any(item["capability"] == "attachments" for item in report["capabilities"])
    checks = {item["name"]: item for item in report["checks"]}
    for name in (
        "AIAgent.run_conversation",
        "SessionDB.get_messages_as_conversation",
        "SessionDB.delete_session",
        "tools.approval.register_gateway_notify",
        "tools.approval.resolve_gateway_approval",
        "BasePlatformAdapter.send",
        "BasePlatformAdapter.send_document",
        "BasePlatformAdapter.send_image_file",
        "BasePlatformAdapter.send_video",
        "BasePlatformAdapter.set_message_handler",
        "WeixinAdapter.send",
        "WeixinAdapter.send_document",
        "WeixinAdapter.send_image_file",
        "WeixinAdapter.send_video",
        "provider_registry_hermes_mapping",
    ):
        assert checks[name]["ok"] is True


def test_runtime_and_doctor_expose_hermes_compatibility(daemon_client):
    runtime = daemon_client.client.get("/runtime/info", headers=daemon_client.headers)
    assert runtime.status_code == 200
    assert runtime.json()["hermes_compatibility"]["ok"] is True

    doctor = daemon_client.client.get("/doctor/run", headers=daemon_client.headers)
    assert doctor.status_code == 200
    body = doctor.json()
    assert body["hermes_compatibility"]["ok"] is True
    assert any(item["name"] == "hermes_compat:WeixinAdapter.send_document" for item in body["checks"])


def test_file_question_uses_normal_chat_path(daemon_client, monkeypatch):
    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        return {
            "ok": True,
            "reply": f"normal chat: {message}",
            "engine": "hermes_agent_loop",
            "provider": "unit",
            "model": "unit-model",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": bool(conversation_id),
        }

    monkeypatch.setattr(daemon_client.app_module, "send_agent_message", fake_send_agent_message)

    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你能不能传附件？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "hermes_agent_loop"
    assert body["reply"] == "normal chat: 你能不能传附件？"


def test_weixin_file_question_uses_normal_chat_path(daemon_client, monkeypatch):
    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        return {
            "ok": True,
            "reply": f"normal weixin chat: {message}",
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
                text="你支持发文件或附件吗",
                media_urls=[],
                media_types=[],
                message_id="wx_file_question",
                source=SimpleNamespace(chat_id="wx_user", user_id="wx_user", chat_type="dm"),
            ),
            daemon_client.config_paths.get_runtime_paths(),
        )
    )

    assert result["ok"] is True
    assert result["intent"]["kind"] == "chat_message"
    assert result["chat"]["engine"] == "hermes_agent_loop"
    assert result["chat"]["reply"] == "normal weixin chat: 你支持发文件或附件吗"
