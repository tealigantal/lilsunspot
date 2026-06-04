import importlib
import json
from typing import Any

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


class FakeChatResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeChatClient:
    def __init__(self, response: FakeChatResponse):
        self.response = response
        self.requests: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None

    async def post(self, path: str, headers: dict[str, str], json: dict[str, Any]):
        self.requests.append({"path": path, "headers": headers, "json": json})
        return self.response


def test_chat_send_requires_token(tmp_path, monkeypatch):
    _chat_client, _config_paths, _hermes_runtime, client, _headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", json={"message": "你好"})

    assert response.status_code == 403


def test_chat_send_empty_message_returns_human_error(tmp_path, monkeypatch):
    _chat_client, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", headers=headers, json={"message": "   "})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "empty_message"
    assert "输入" in body["message"]


def test_chat_send_unconfigured_returns_human_error(tmp_path, monkeypatch):
    _chat_client, _config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "setup_required"
    assert "首启向导" in body["message"]


def test_chat_send_cloud_missing_key_returns_human_error_without_runtime_call(tmp_path, monkeypatch):
    chat_client, config_paths, _hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    paths = config_paths.get_runtime_paths()
    (paths.hermes_home / "config.yaml").write_text(
        "\n".join(
            [
                "model:",
                "  provider: deepseek",
                "  default: deepseek-chat",
                "  base_url: https://api.deepseek.com/v1",
                "lilsunspot:",
                "  provider: deepseek",
                "  model: deepseek-chat",
            ]
        ),
        encoding="utf-8",
    )

    def fail_if_called(_base_url: str):
        raise AssertionError("runtime adapter should not be called without a cloud API key")

    monkeypatch.setattr(chat_client, "_make_http_client", fail_if_called)

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "missing_api_key"
    assert "API Key" in body["message"]


def test_chat_send_real_adapter_success_after_local_provider_save(tmp_path, monkeypatch):
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
    fake_client = FakeChatClient(
        FakeChatResponse(
            200,
            {"choices": [{"message": {"content": "你好，我是小黑子。"}}]},
        )
    )
    base_urls: list[str] = []

    def make_client(base_url: str):
        base_urls.append(base_url)
        return fake_client

    monkeypatch.setattr(chat_client, "_make_http_client", make_client)

    response = client.post("/chat/send", headers=headers, json={"message": "你好"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "hermes_runtime_adapter"
    assert body["reply"] == "你好，我是小黑子。"
    assert body["provider"] == "ollama"
    assert body["model"] == "llama3.2"
    assert base_urls == ["http://127.0.0.1:11434/v1/"]
    assert fake_client.requests[0]["path"] == "chat/completions"
    assert fake_client.requests[0]["json"]["model"] == "llama3.2"
    assert fake_client.requests[0]["json"]["messages"] == [{"role": "user", "content": "你好"}]
    assert "Authorization" not in fake_client.requests[0]["headers"]


def test_chat_send_reads_cloud_key_from_lilsunspot_hermes_home_and_redacts(tmp_path, monkeypatch):
    chat_client, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    secret = "placeholder-runtime-secret"
    provider = {
        "id": "deepseek",
        "type": "cloud",
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "hermes_provider": "deepseek",
    }
    hermes_runtime.save_provider_credentials(
        provider,
        "deepseek-chat",
        secret,
        paths=config_paths.get_runtime_paths(),
    )
    fake_client = FakeChatClient(
        FakeChatResponse(
            200,
            {"choices": [{"message": {"content": "真实回复"}}]},
        )
    )
    monkeypatch.setattr(chat_client, "_make_http_client", lambda _base_url: fake_client)

    response = client.post("/chat/send", headers=headers, json={"message": "测试"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reply"] == "真实回复"
    assert fake_client.requests[0]["headers"]["Authorization"] == f"Bearer {secret}"
    assert secret not in response.text
    assert config_paths.get_runtime_paths().hermes_home == (tmp_path / "data" / "hermes_home").resolve()


def test_chat_send_runtime_error_is_plain_chinese_and_redacted(tmp_path, monkeypatch):
    chat_client, config_paths, hermes_runtime, client, headers = _load_test_app(tmp_path, monkeypatch)
    secret = "placeholder-runtime-secret"
    provider = {
        "id": "deepseek",
        "type": "cloud",
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "hermes_provider": "deepseek",
    }
    hermes_runtime.save_provider_credentials(
        provider,
        "deepseek-chat",
        secret,
        paths=config_paths.get_runtime_paths(),
    )
    fake_client = FakeChatClient(
        FakeChatResponse(
            401,
            {"error": {"message": f"invalid key {secret}"}},
        )
    )
    monkeypatch.setattr(chat_client, "_make_http_client", lambda _base_url: fake_client)

    response = client.post("/chat/send", headers=headers, json={"message": "测试"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "runtime_auth_failed"
    assert "鉴权" in body["message"]
    assert secret not in response.text
