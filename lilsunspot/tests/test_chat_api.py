import importlib
import json

import httpx
from fastapi.testclient import TestClient


def _load_test_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(tmp_path / "data"))

    import lilsunspot.daemon.auth as auth
    import lilsunspot.daemon.chat_client as chat_client
    import lilsunspot.daemon.config_paths as config_paths
    import lilsunspot.daemon.hermes_runtime as hermes_runtime
    import lilsunspot.daemon.provider_client as provider_client
    import lilsunspot.daemon.app as app_module

    importlib.reload(config_paths)
    importlib.reload(auth)
    importlib.reload(provider_client)
    chat_client = importlib.reload(chat_client)
    hermes_runtime = importlib.reload(hermes_runtime)
    app_module = importlib.reload(app_module)

    client = TestClient(app_module.app)
    token = json.loads(config_paths.get_runtime_paths().token_file.read_text(encoding="utf-8"))["token"]
    headers = {auth.TOKEN_HEADER: token}
    return chat_client, config_paths, hermes_runtime, client, headers


def _mock_chat_http_client(chat_client, monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def make_client(base_url: str):
        return httpx.AsyncClient(base_url=base_url, transport=transport)

    monkeypatch.setattr(chat_client, "_make_chat_http_client", make_client)


def test_chat_send_requires_token(tmp_path, monkeypatch):
    _chat_client, _config_paths, _hermes_runtime, client, _headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", json={"message": "你好"})

    assert response.status_code == 403


def test_chat_send_unconfigured_returns_human_error(tmp_path, monkeypatch):
    _chat_client, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "setup_required"
    assert "还没有设置 AI 服务" in body["message"]


def test_chat_send_uses_runtime_after_local_provider_save(tmp_path, monkeypatch):
    chat_client, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
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
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        assert request.headers.get("authorization") is None
        return httpx.Response(200, json={"choices": [{"message": {"content": "本地模型回复。"}}]})

    _mock_chat_http_client(chat_client, monkeypatch, handler)

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "lilsunspot_provider_adapter"
    assert body["reply"] == "本地模型回复。"
    assert seen_payload["model"] == "llama3.2"
    default_hint = client.get("/modes/current", headers=headers).json()["profile"]["system_hint"]
    assert seen_payload["messages"] == [
        {"role": "system", "content": default_hint},
        {"role": "user", "content": "你好"},
    ]


def test_chat_send_uses_selected_mode_system_hint_from_lilsunspot_data_dir(tmp_path, monkeypatch):
    chat_client, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
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
    selected_hint = selected.json()["profile"]["system_hint"]
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        assert request.headers.get("authorization") is None
        return httpx.Response(200, json={"choices": [{"message": {"content": "已按务实模式回复。"}}]})

    _mock_chat_http_client(chat_client, monkeypatch, handler)

    response = client.post("/chat/send", headers=headers, json={"message": "帮我整理下一步"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert paths.data_dir == (tmp_path / "data").resolve()
    assert (paths.data_dir / "mode-profile.json").exists()
    assert not (paths.hermes_home / "mode-profile.json").exists()
    assert seen_payload["messages"] == [
        {"role": "system", "content": selected_hint},
        {"role": "user", "content": "帮我整理下一步"},
    ]


def test_chat_send_uses_mode_sliders_in_next_system_hint(tmp_path, monkeypatch):
    chat_client, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
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
    assert selected.json()["profile"]["style_axis"] == 80
    assert "当前输出偏好" in selected.json()["profile"]["system_hint"]
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"choices": [{"message": {"content": "已按滑杆偏好回复。"}}]})

    _mock_chat_http_client(chat_client, monkeypatch, handler)

    response = client.post("/chat/send", headers=headers, json={"message": "下一步做什么"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    system_hint = seen_payload["messages"][0]["content"]
    assert "当前输出偏好" in system_hint
    assert "表达更有陪伴感" in system_hint
    assert "回答保持简短" in system_hint
    assert "风险或不确定时优先确认" in system_hint
