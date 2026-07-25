from __future__ import annotations


DEEPSEEK_PROVIDER = {
    "id": "deepseek",
    "type": "cloud",
    "env_key": "DEEPSEEK_API_KEY",
    "base_url": "https://api.deepseek.com/v1",
    "hermes_provider": "deepseek",
}


def _save_deepseek(daemon_client, api_key: str = "placeholder-chat-runtime-key") -> None:
    daemon_client.hermes_runtime.save_provider_credentials(
        DEEPSEEK_PROVIDER,
        "deepseek-chat",
        api_key,
        paths=daemon_client.config_paths.get_runtime_paths(),
    )


def test_chat_runtime_cloud_provider_uses_hermes_agent_loop_without_leaking(daemon_client, monkeypatch):
    secret = "placeholder-chat-runtime-key"
    seen = {}
    _save_deepseek(daemon_client, secret)

    def fake_run_agent_turn(**kwargs):
        seen.update(kwargs)
        return {
            "ok": True,
            "reply": "收到。",
            "engine": "hermes_agent_loop",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "conversation_id": kwargs["conversation_id"],
            "conversation_id_supported": True,
            "conversation_id_requested": True,
            "hermes_session_id": kwargs["conversation_id"],
        }

    monkeypatch.setattr(daemon_client.agent_runner, "_run_agent_turn", fake_run_agent_turn)

    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "hermes_agent_loop"
    assert body["conversation_id"] == "personal"
    assert body["conversation_id_supported"] is True
    assert body["reply"] == "收到。"
    assert seen["message"] == "你好"
    assert seen["conversation_id"] == "personal"
    assert seen["settings"]["api_key"] == secret
    assert seen["settings"]["hermes_provider"] == "deepseek"
    assert seen["settings"]["model"] == "deepseek-chat"
    default_hint = daemon_client.client.get("/modes/current", headers=daemon_client.headers).json()["prompt"][
        "system_hint"
    ]
    assert "你是 Lilsunspot 小黑子" in seen["settings"]["system_hint"]
    assert default_hint in seen["settings"]["system_hint"]
    generation = seen["settings"]["generation_control"]
    assert generation["runtime"]["max_tokens"] == 1200
    assert generation["runtime"]["max_iterations"] == 24
    assert generation["runtime"]["request_overrides"] == {"temperature": 0.6}
    assert generation["runtime"]["reasoning_effort"] is None
    assert "当前 Mode 运行策略" not in seen["settings"]["system_hint"]
    assert "当前 lilsunspot 能力状态快照" in seen["settings"]["system_hint"]
    assert "provider=deepseek；model=deepseek-chat" in seen["settings"]["system_hint"]
    assert "runtime.desktop_image_upload / 桌面聊天图片上传: status=enabled" in seen["settings"]["system_hint"]
    assert secret not in response.text


def test_chat_runtime_requires_provider_config_before_agent_loop(daemon_client, monkeypatch):
    called = False

    def fake_run_agent_turn(**kwargs):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(daemon_client.agent_runner, "_run_agent_turn", fake_run_agent_turn)

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
    assert called is False


def test_chat_runtime_agent_loop_errors_are_human_error(daemon_client, monkeypatch):
    _save_deepseek(daemon_client)

    def fake_run_agent_turn(**kwargs):
        raise RuntimeError("provider secret should not leak")

    monkeypatch.setattr(daemon_client.agent_runner, "_run_agent_turn", fake_run_agent_turn)

    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "unknown"
    assert "聊天请求没有成功" in body["message"]
