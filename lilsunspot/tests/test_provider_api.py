import importlib
import json
from pathlib import Path

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
    importlib.reload(chat_client)
    importlib.reload(hermes_runtime)
    app_module = importlib.reload(app_module)

    client = TestClient(app_module.app)
    token = json.loads(config_paths.get_runtime_paths().token_file.read_text(encoding="utf-8"))["token"]
    headers = {auth.TOKEN_HEADER: token}
    return app_module, config_paths, client, headers


def test_providers_test_requires_token(tmp_path, monkeypatch):
    _app_module, _config_paths, client, _headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post(
        "/providers/test",
        json={"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "placeholder-no-token"},
    )

    assert response.status_code == 403


def test_providers_test_mock_success(tmp_path, monkeypatch):
    app_module, _config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)

    async def fake_test_provider_connection(provider, model, api_key, base_url_override=None):
        assert base_url_override == ""
        return {
            "ok": True,
            "provider": provider["id"],
            "model": model,
            "message": "连接测试成功。",
        }

    monkeypatch.setattr(app_module, "test_provider_connection", fake_test_provider_connection)

    response = client.post(
        "/providers/test",
        headers=headers,
        json={"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "placeholder-success"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_providers_test_mock_401_is_redacted(tmp_path, monkeypatch):
    app_module, _config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)
    secret = "placeholder-provider-api-invalid"

    async def fake_test_provider_connection(provider, model, api_key, base_url_override=None):
        return {
            "ok": False,
            "provider": provider["id"],
            "model": model,
            "error_code": "invalid_key",
            "message": "API Key 无效或没有权限。",
            "suggestion": "请重新检查 API Key 是否完整、是否属于当前服务商。",
        }

    monkeypatch.setattr(app_module, "test_provider_connection", fake_test_provider_connection)

    response = client.post(
        "/providers/test",
        headers=headers,
        json={"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": secret},
    )

    assert response.status_code == 200
    assert response.json()["error_code"] == "invalid_key"
    assert secret not in response.text


def test_providers_test_mock_network_error(tmp_path, monkeypatch):
    app_module, _config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)

    async def fake_test_provider_connection(provider, model, api_key, base_url_override=None):
        return {
            "ok": False,
            "provider": provider["id"],
            "model": model,
            "error_code": "network_error",
            "message": "无法连接模型服务。",
            "suggestion": "请检查网络、base_url、代理设置，或稍后再试。",
        }

    monkeypatch.setattr(app_module, "test_provider_connection", fake_test_provider_connection)

    response = client.post(
        "/providers/test",
        headers=headers,
        json={"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "placeholder-network"},
    )

    assert response.status_code == 200
    assert response.json()["error_code"] == "network_error"


def test_save_provider_writes_only_lilsunspot_data_dir(tmp_path, monkeypatch):
    _app_module, config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)
    secret = "placeholder-save-provider-temp-only"

    response = client.post(
        "/providers/save",
        headers=headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": secret},
    )

    assert response.status_code == 200
    paths = config_paths.get_runtime_paths()
    assert paths.data_dir == (tmp_path / "data").resolve()
    assert (paths.hermes_home / ".env").exists()
    assert (paths.hermes_home / "config.yaml").exists()
    assert Path(response.json()["hermes_home"]) == paths.hermes_home


def test_save_provider_supports_model_and_base_url_override(tmp_path, monkeypatch):
    _app_module, config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post(
        "/providers/save",
        headers=headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-reasoner",
            "api_key": "placeholder-save-provider-override",
            "base_url_override": "https://api.deepseek.com/v1",
        },
    )

    assert response.status_code == 200
    config_text = (config_paths.get_runtime_paths().hermes_home / "config.yaml").read_text(encoding="utf-8")
    assert "deepseek-reasoner" in config_text
    assert "https://api.deepseek.com/v1" in config_text


def test_save_provider_does_not_require_successful_test(tmp_path, monkeypatch):
    app_module, config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)

    async def fake_test_provider_connection(provider, model, api_key, base_url_override=None):
        return {
            "ok": False,
            "provider": provider["id"],
            "model": model,
            "error_code": "network_error",
            "message": "无法连接模型服务。",
            "suggestion": "请稍后再试。",
        }

    monkeypatch.setattr(app_module, "test_provider_connection", fake_test_provider_connection)

    test_response = client.post(
        "/providers/test",
        headers=headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": "placeholder-save-without-test"},
    )
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is False

    save_response = client.post(
        "/providers/save",
        headers=headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": "placeholder-save-without-test"},
    )

    assert save_response.status_code == 200
    assert save_response.json()["ok"] is True
    config_text = (config_paths.get_runtime_paths().hermes_home / "config.yaml").read_text(encoding="utf-8")
    assert "deepseek-chat" in config_text


def test_save_local_provider_allows_empty_key(tmp_path, monkeypatch):
    _app_module, config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)

    response = client.post(
        "/providers/save",
        headers=headers,
        json={"provider": "ollama", "model": "llama3.2", "api_key": ""},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"
    assert (config_paths.get_runtime_paths().hermes_home / "config.yaml").exists()


def test_providers_test_local_provider_allows_empty_key(tmp_path, monkeypatch):
    app_module, _config_paths, client, headers = _load_test_app(tmp_path, monkeypatch)

    async def fake_test_provider_connection(provider, model, api_key, base_url_override=None):
        assert provider["id"] == "ollama"
        assert api_key == ""
        return {"ok": True, "provider": "ollama", "model": model, "message": "本地服务可用。"}

    monkeypatch.setattr(app_module, "test_provider_connection", fake_test_provider_connection)

    response = client.post(
        "/providers/test",
        headers=headers,
        json={"provider": "ollama", "model": "llama3.2", "api_key": ""},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
