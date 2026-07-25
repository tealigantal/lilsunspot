import importlib
import json

from fastapi.testclient import TestClient


def _load_test_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(tmp_path / "data"))

    import lilsunspot.daemon.auth as auth
    import lilsunspot.daemon.agent_host as agent_host
    import lilsunspot.daemon.agent_runner as agent_runner
    import lilsunspot.daemon.chat_client as chat_client
    import lilsunspot.daemon.config_paths as config_paths
    import lilsunspot.daemon.hermes_runtime as hermes_runtime
    import lilsunspot.daemon.provider_client as provider_client
    import lilsunspot.daemon.app as app_module

    importlib.reload(config_paths)
    importlib.reload(auth)
    agent_host = importlib.reload(agent_host)
    agent_host.reset_for_tests()
    importlib.reload(provider_client)
    chat_client = importlib.reload(chat_client)
    agent_runner = importlib.reload(agent_runner)
    hermes_runtime = importlib.reload(hermes_runtime)
    app_module = importlib.reload(app_module)

    client = TestClient(app_module.app)
    token = json.loads(config_paths.get_runtime_paths().token_file.read_text(encoding="utf-8"))["token"]
    headers = {auth.TOKEN_HEADER: token}
    return agent_runner, config_paths, hermes_runtime, client, headers


def _mock_agent_turn(agent_runner, monkeypatch, reply: str):
    seen = {}

    def fake_run_agent_turn(**kwargs):
        seen.update(kwargs)
        return {
            "ok": True,
            "reply": reply,
            "engine": "hermes_agent_loop",
            "provider": kwargs["settings"]["provider"],
            "model": kwargs["settings"]["model"],
            "conversation_id": kwargs["conversation_id"],
            "conversation_id_supported": True,
            "conversation_id_requested": True,
        }

    monkeypatch.setattr(agent_runner, "_run_agent_turn", fake_run_agent_turn)
    return seen


def _prompt_layer_ids(mode_response):
    return [layer["id"] for layer in mode_response["prompt"]["layers"]]


def test_chat_send_requires_token(tmp_path, monkeypatch):
    _agent_runner, _config_paths, _hermes_runtime, client, _headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", json={"message": "你好"})

    assert response.status_code == 403


def test_chat_send_unconfigured_returns_human_error(tmp_path, monkeypatch):
    _agent_runner, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "setup_required"
    assert "还没有设置 AI 服务" in body["message"]


def test_chat_send_uses_runtime_after_local_provider_save(tmp_path, monkeypatch):
    agent_runner, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    provider = {
        "id": "ollama",
        "type": "local",
        "env_key": "OLLAMA_API_KEY",
        "base_url": "http://127.0.0.1:11434/v1",
        "hermes_provider": "custom",
    }
    hermes_runtime.save_provider_credentials(
        provider,
        "llama3.2",
        "",
        paths=config_paths.get_runtime_paths(),
    )
    seen = _mock_agent_turn(agent_runner, monkeypatch, "本地模型回复。")

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "hermes_agent_loop"
    assert body["reply"] == "本地模型回复。"
    assert seen["settings"]["model"] == "llama3.2"
    assert seen["settings"]["hermes_provider"] == "custom"
    current_mode = client.get("/modes/current", headers=headers).json()
    default_hint = current_mode["prompt"]["system_hint"]
    assert current_mode["profile"]["system_hint"] == default_hint
    assert _prompt_layer_ids(current_mode) == ["mode_profile", "slider_overrides"]
    assert "当前表达风格" in default_hint
    assert "当前措辞偏好" in default_hint
    assert "你是 Lilsunspot 小黑子" in seen["settings"]["system_hint"]
    assert default_hint in seen["settings"]["system_hint"]
    assert "当前 lilsunspot 能力状态快照" in seen["settings"]["system_hint"]
    assert "runtime.desktop_image_upload / 桌面聊天图片上传: status=enabled" in seen["settings"]["system_hint"]
    assert seen["message"] == "你好"


def test_chat_send_uses_selected_mode_system_hint_from_lilsunspot_data_dir(tmp_path, monkeypatch):
    agent_runner, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    provider = {
        "id": "ollama",
        "type": "local",
        "env_key": "OLLAMA_API_KEY",
        "base_url": "http://127.0.0.1:11434/v1",
        "hermes_provider": "custom",
    }
    paths = config_paths.get_runtime_paths()
    hermes_runtime.save_provider_credentials(provider, "llama3.2", "", paths=paths)
    selected = client.post("/modes/select", headers=headers, json={"mode": "pragmatic"})
    assert selected.status_code == 200
    selected_mode = selected.json()
    selected_hint = selected_mode["prompt"]["system_hint"]
    assert selected_mode["profile"]["system_hint"] == selected_hint
    assert selected_mode["prompt"]["layers"][0]["summary"] == "偏务实的措辞，减少铺垫，直接表达重点。"
    seen = _mock_agent_turn(agent_runner, monkeypatch, "已按务实模式回复。")

    response = client.post("/chat/send", headers=headers, json={"message": "帮我整理下一步"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert paths.data_dir == (tmp_path / "data").resolve()
    assert (paths.data_dir / "mode-profile.json").exists()
    assert not (paths.hermes_home / "mode-profile.json").exists()
    assert "你是 Lilsunspot 小黑子" in seen["settings"]["system_hint"]
    assert selected_hint in seen["settings"]["system_hint"]
    assert "当前 lilsunspot 能力状态快照" in seen["settings"]["system_hint"]
    assert "runtime.desktop_image_upload / 桌面聊天图片上传: status=enabled" in seen["settings"]["system_hint"]
    assert seen["message"] == "帮我整理下一步"


def test_conversation_mode_override_persists_and_stays_isolated(tmp_path, monkeypatch):
    agent_runner, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    provider = {
        "id": "ollama",
        "type": "local",
        "env_key": "OLLAMA_API_KEY",
        "base_url": "http://127.0.0.1:11434/v1",
        "hermes_provider": "custom",
    }
    paths = config_paths.get_runtime_paths()
    hermes_runtime.save_provider_credentials(provider, "llama3.2", "", paths=paths)
    first = client.post("/conversations", headers=headers, json={"title": "A"}).json()["conversation"]
    second = client.post("/conversations", headers=headers, json={"title": "B"}).json()["conversation"]

    selected = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "pragmatic", "conversation_id": first["id"], "scope": "conversation"},
    )

    assert selected.status_code == 200
    assert selected.json()["current"] == "pragmatic"
    assert selected.json()["scope"] == "conversation"
    assert selected.json()["conversation_id"] == first["id"]
    assert client.get(f"/modes/current?conversation_id={first['id']}", headers=headers).json()["current"] == "pragmatic"
    assert client.get(f"/modes/current?conversation_id={second['id']}", headers=headers).json()["current"] == "balanced"
    assert client.get("/modes/current", headers=headers).json()["current"] == "balanced"

    seen = _mock_agent_turn(agent_runner, monkeypatch, "会话模式回复。")
    response = client.post(
        "/chat/send",
        headers=headers,
        json={"conversation_id": first["id"], "message": "帮我整理下一步"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "当前表达风格：pragmatic" in seen["settings"]["system_hint"]

    _agent_runner, _config_paths, _hermes_runtime, reloaded_client, reloaded_headers = _load_test_app(tmp_path, monkeypatch)
    persisted = reloaded_client.get(f"/modes/current?conversation_id={first['id']}", headers=reloaded_headers)
    assert persisted.status_code == 200
    assert persisted.json()["current"] == "pragmatic"

    deleted = reloaded_client.delete(f"/conversations/{first['id']}", headers=reloaded_headers)
    assert deleted.status_code == 200
    fallback = reloaded_client.get(f"/modes/current?conversation_id={first['id']}", headers=reloaded_headers)
    assert fallback.status_code == 200
    assert fallback.json()["current"] == "balanced"
    assert fallback.json()["scope"] == "global"


def test_weixin_conversation_modes_are_independent(tmp_path, monkeypatch):
    _agent_runner, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    first = client.post(
        "/conversations",
        headers=headers,
        json={
            "title": "微信 A",
            "kind": "weixin",
            "metadata": {"weixin_route": {"account_id": "unit", "chat_id": "wx-a", "user_id": "wx-a"}},
        },
    ).json()["conversation"]
    second = client.post(
        "/conversations",
        headers=headers,
        json={
            "title": "微信 B",
            "kind": "weixin",
            "metadata": {"weixin_route": {"account_id": "unit", "chat_id": "wx-b", "user_id": "wx-b"}},
        },
    ).json()["conversation"]

    first_result = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "pragmatic", "conversation_id": first["id"], "scope": "conversation"},
    )
    second_result = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "emotional", "conversation_id": second["id"], "scope": "conversation"},
    )

    assert first_result.status_code == 200
    assert second_result.status_code == 200
    assert client.get(f"/modes/current?conversation_id={first['id']}", headers=headers).json()["current"] == "pragmatic"
    assert client.get(f"/modes/current?conversation_id={second['id']}", headers=headers).json()["current"] == "emotional"


def test_turn_mode_override_does_not_persist(tmp_path, monkeypatch):
    _agent_runner, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)

    turn = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "pragmatic", "conversation_id": "personal", "scope": "turn"},
    )

    assert turn.status_code == 200
    assert turn.json()["current"] == "pragmatic"
    assert turn.json()["scope"] == "turn"
    persisted = client.get("/modes/current?conversation_id=personal", headers=headers)
    assert persisted.status_code == 200
    assert persisted.json()["current"] == "balanced"
    assert persisted.json()["scope"] == "global"


def test_chat_send_uses_mode_sliders_in_next_system_hint(tmp_path, monkeypatch):
    agent_runner, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    provider = {
        "id": "ollama",
        "type": "local",
        "env_key": "OLLAMA_API_KEY",
        "base_url": "http://127.0.0.1:11434/v1",
        "hermes_provider": "custom",
    }
    hermes_runtime.save_provider_credentials(provider, "llama3.2", "", paths=config_paths.get_runtime_paths())
    selected = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "balanced", "style_axis": 80, "detail_level": 25, "autonomy_level": 20},
    )
    assert selected.status_code == 200
    assert selected.json()["current"] == "custom"
    assert selected.json()["profile"]["style_axis"] == 80
    assert "当前措辞偏好" in selected.json()["profile"]["system_hint"]
    assert selected.json()["prompt"]["slider_summary"] == selected.json()["prompt"]["layers"][1]["summary"]
    seen = _mock_agent_turn(agent_runner, monkeypatch, "已按滑杆偏好回复。")

    response = client.post("/chat/send", headers=headers, json={"message": "下一步做什么"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    system_hint = seen["settings"]["system_hint"]
    assert "当前措辞偏好" in system_hint
    assert "表达更有陪伴感" in system_hint
    assert "回答长度、推理深度和行动次数由独立的生成控制决定" in system_hint
    assert "当前 Mode 运行策略" not in system_hint
    assert "目标约 600 tokens" not in system_hint
    assert seen["settings"]["generation_control"]["mode"] == "balanced"


def test_mode_prompt_compiles_defaults_and_clamps_saved_sliders(tmp_path, monkeypatch):
    _agent_runner, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)

    default_response = client.get("/modes/current", headers=headers)
    assert default_response.status_code == 200
    default_mode = default_response.json()
    assert default_mode["current"] == "balanced"
    assert default_mode["profile"]["style_axis"] == 45
    assert default_mode["profile"]["detail_level"] == 60
    assert default_mode["profile"]["autonomy_level"] == 60
    assert _prompt_layer_ids(default_mode) == ["mode_profile", "slider_overrides"]
    assert "表达平衡清楚" in default_mode["prompt"]["slider_summary"]
    assert default_mode["profile"]["system_hint"] == default_mode["prompt"]["system_hint"]

    fixed = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "balanced", "style_axis": 45, "detail_level": 60, "autonomy_level": 60},
    )
    assert fixed.status_code == 200
    assert fixed.json()["current"] == "balanced"

    selected = client.post(
        "/modes/select",
        headers=headers,
        json={"mode": "emotional", "style_axis": -20, "detail_level": 140},
    )

    assert selected.status_code == 200
    body = selected.json()
    assert body["current"] == "custom"
    assert body["profile"]["style_axis"] == 0
    assert body["profile"]["detail_level"] == 100
    assert body["profile"]["autonomy_level"] == 45
    assert "表达更务实" in body["prompt"]["slider_summary"]
    assert "回答长度、推理深度和行动次数由独立的生成控制决定" in body["prompt"]["slider_summary"]


def test_mismatched_fixed_mode_state_reads_as_custom(tmp_path, monkeypatch):
    _agent_runner, config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    paths = config_paths.get_runtime_paths()
    (paths.data_dir / "mode-profile.json").write_text(
        json.dumps(
            {
                "mode": "balanced",
                "sliders": {"style_axis": 80, "detail_level": 25, "autonomy_level": 20},
            }
        ),
        encoding="utf-8",
    )

    current = client.get("/modes/current", headers=headers)

    assert current.status_code == 200
    body = current.json()
    assert body["current"] == "custom"
    assert body["profile"]["style_axis"] == 80
    assert body["profile"]["detail_level"] == 25
    assert body["profile"]["autonomy_level"] == 20
