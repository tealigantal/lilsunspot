from __future__ import annotations


def test_runtime_mode_gateway_safety_and_doctor_skeletons(daemon_client):
    client = daemon_client.client
    headers = daemon_client.headers

    runtime = client.get("/runtime/info", headers=headers)
    assert runtime.status_code == 200
    assert runtime.json()["bind_host"] == "127.0.0.1"
    assert runtime.json()["bind_port"] == 8765
    assert runtime.json()["base_url"] == "http://127.0.0.1:8765"

    modes = client.get("/modes", headers=headers)
    assert modes.status_code == 200
    mode_ids = {item["id"] for item in modes.json()["modes"]}
    assert {"pragmatic", "balanced", "emotional", "custom"} <= mode_ids
    assert "default" not in mode_ids

    selected = client.post("/modes/select", headers=headers, json={"mode": "balanced"})
    assert selected.status_code == 200
    assert selected.json()["current"] == "balanced"
    assert selected.json()["profile"]["system_hint"] == selected.json()["prompt"]["system_hint"]
    assert [layer["id"] for layer in selected.json()["prompt"]["layers"]] == [
        "product_baseline",
        "mode_profile",
        "slider_overrides",
    ]

    weixin = client.get("/gateway/weixin/status", headers=headers)
    assert weixin.status_code == 200
    assert weixin.json()["connected"] is False
    assert weixin.json()["status"] in {"not_configured", "error"}
    assert weixin.json()["capabilities"]["official_payment_or_materials_required"] is False

    commands = client.get("/gateway/weixin/commands", headers=headers)
    assert commands.status_code == 200
    assert commands.json()["commands"]
    command_names = {item["name"] for item in commands.json()["commands"]}
    assert {"/help", "/mode"} <= command_names
    assert "/approve" not in command_names
    assert "/reject" not in command_names

    policy = client.get("/safety/policy", headers=headers)
    assert policy.status_code == 200
    assert policy.json()["policy"]["high_risk"]["requires_approval"] is True

    approvals = client.get("/safety/approvals", headers=headers)
    assert approvals.status_code == 200
    assert approvals.json()["pending"] == []

    doctor = client.get("/doctor/run", headers=headers)
    assert doctor.status_code == 200
    assert doctor.json()["ok"] is True

    repair = client.post("/doctor/repair", headers=headers, json={"check_name": "daemon_responding"})
    assert repair.status_code == 200
    assert repair.json()["ok"] is False
    assert "占位" in repair.json()["message"]


def test_chat_runtime_requires_provider_config(daemon_client):
    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "setup_required"
    assert "还没有设置 AI 服务" in body["message"]


def test_chat_runtime_after_provider_save(daemon_client, monkeypatch):
    client = daemon_client.client
    headers = daemon_client.headers
    seen = {}

    def fake_run_agent_turn(**kwargs):
        seen.update(kwargs)
        return {
            "ok": True,
            "reply": "这是模型回复。",
            "engine": "hermes_agent_loop",
            "provider": "ollama",
            "model": "llama3.2",
            "conversation_id": kwargs["conversation_id"],
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "_run_agent_turn", fake_run_agent_turn)

    save = client.post(
        "/providers/save",
        headers=headers,
        json={"provider": "ollama", "model": "llama3.2", "api_key": ""},
    )
    assert save.status_code == 200

    response = client.post(
        "/chat/send",
        headers=headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "hermes_agent_loop"
    assert body["reply"] == "这是模型回复。"
    assert seen["settings"]["model"] == "llama3.2"
    assert seen["settings"]["hermes_provider"] == "custom"
    default_hint = client.get("/modes/current", headers=headers).json()["prompt"]["system_hint"]
    assert seen["settings"]["system_hint"].startswith(default_hint)
    assert "当前 lilsunspot 能力状态快照" in seen["settings"]["system_hint"]
    assert "runtime.desktop_image_upload / 桌面聊天图片上传: status=enabled" in seen["settings"]["system_hint"]


def test_weixin_private_text_uses_hermes_agent_loop(daemon_client, monkeypatch):
    client = daemon_client.client
    headers = daemon_client.headers
    seen = {}

    async def fake_send_agent_message(message, conversation_id=None, paths=None, **kwargs):
        seen["message"] = message
        seen["conversation_id"] = conversation_id
        return {
            "ok": True,
            "reply": "微信私聊回复。",
            "engine": "hermes_agent_loop",
            "provider": "ollama",
            "model": "llama3.2",
            "conversation_id": conversation_id,
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(daemon_client.agent_runner, "send_agent_message", fake_send_agent_message)

    save = client.post(
        "/providers/save",
        headers=headers,
        json={"provider": "ollama", "model": "llama3.2", "api_key": ""},
    )
    assert save.status_code == 200

    response = client.post(
        "/gateway/weixin/commands/handle",
        headers=headers,
        json={"text": "帮我总结今天安排"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["intent"]["kind"] == "chat_message"
    assert body["chat"]["engine"] == "hermes_agent_loop"
    assert body["chat"]["reply"] == "微信私聊回复。"
    assert seen["message"] == "帮我总结今天安排"
    assert seen["conversation_id"] == "personal"
