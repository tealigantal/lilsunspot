from __future__ import annotations

import json

import httpx


def _mock_chat_http_client(daemon_client, monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def make_client(base_url: str):
        return httpx.AsyncClient(base_url=base_url, transport=transport)

    monkeypatch.setattr(daemon_client.chat_client, "_make_chat_http_client", make_client)


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
    assert any(item["id"] == "default" for item in modes.json()["modes"])

    selected = client.post("/modes/select", headers=headers, json={"mode": "default"})
    assert selected.status_code == 200
    assert selected.json()["current"] == "default"
    assert selected.json()["profile"]["system_hint"] == selected.json()["prompt"]["system_hint"]
    assert [layer["id"] for layer in selected.json()["prompt"]["layers"]] == [
        "product_baseline",
        "mode_profile",
        "slider_overrides",
    ]

    weixin = client.get("/gateway/weixin/status", headers=headers)
    assert weixin.status_code == 200
    assert weixin.json()["connected"] is False
    assert "不会扫码登录" in weixin.json()["message"]

    commands = client.get("/gateway/weixin/commands", headers=headers)
    assert commands.status_code == 200
    assert commands.json()["commands"]
    assert any(item["name"] == "/approve" for item in commands.json()["commands"])

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
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        assert request.headers.get("authorization") is None
        assert str(request.url) == "http://127.0.0.1:11434/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "这是模型回复。"}}]})

    _mock_chat_http_client(daemon_client, monkeypatch, handler)

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
    assert body["engine"] == "lilsunspot_provider_adapter"
    assert body["reply"] == "这是模型回复。"
    assert seen_payload["model"] == "llama3.2"
    default_hint = client.get("/modes/current", headers=headers).json()["profile"]["system_hint"]
    assert seen_payload["messages"] == [
        {"role": "system", "content": default_hint},
        {"role": "user", "content": "你好"},
    ]
