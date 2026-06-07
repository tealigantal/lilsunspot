from __future__ import annotations

import json


def test_health_is_public_and_providers_require_token(daemon_client):
    client = daemon_client.client

    assert client.get("/health").status_code == 200
    health = client.get("/health").json()
    assert health["ok"] is True
    assert health["status"] == "ready"
    assert health["message_cn"] == "小黑子本地服务正常"
    assert health["setup_required"] is True
    assert client.get("/providers").status_code == 403
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404

    response = client.get("/providers", headers=daemon_client.headers)
    assert response.status_code == 200
    assert len(response.json()["providers"]) >= 1


def test_token_file_written_under_temp_data_dir(daemon_client, tmp_path):
    paths = daemon_client.config_paths.get_runtime_paths()
    token_payload = json.loads(paths.token_file.read_text(encoding="utf-8"))

    assert paths.data_dir == (tmp_path / "data").resolve()
    assert paths.token_file.exists()
    assert token_payload["type"] == "lilsunspot-runtime-token"
    assert token_payload["token"] == daemon_client.token


def test_provider_test_returns_validator_result(daemon_client, monkeypatch):
    async def fake_test_provider_connection(provider, model, api_key, base_url_override=None):
        assert base_url_override == "https://api.deepseek.com/v1"
        return {
            "ok": True,
            "provider": provider["id"],
            "model": model,
            "title": "模型服务连接通过",
            "message": "模型服务已响应，API Key 和模型名称验证通过。",
        }

    monkeypatch.setattr(daemon_client.app_module, "test_provider_connection", fake_test_provider_connection)

    response = daemon_client.client.post(
        "/providers/test",
        headers=daemon_client.headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "placeholder-value",
            "base_url_override": "https://api.deepseek.com/v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "验证通过" in body["message"]


def test_provider_test_error_is_user_facing_and_redacted(daemon_client):
    secret = "placeholder-provider-api-invalid"
    response = daemon_client.client.post(
        "/providers/test",
        headers=daemon_client.headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "invalid_key"
    assert body["title"] == "API Key 可能不正确"
    assert "actions" in body
    assert body["safe_details"]["masked_key"] == ""
    assert secret not in response.text


def test_provider_save_does_not_log_token_or_key(daemon_client):
    client = daemon_client.client
    paths = daemon_client.config_paths.get_runtime_paths()
    local_secret_value = "placeholder-value-for-local-config"

    response = client.post(
        "/providers/save",
        headers=daemon_client.headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": local_secret_value},
    )

    assert response.status_code == 200
    assert (paths.hermes_home / ".env").exists()
    assert (paths.hermes_home / "config.yaml").exists()

    log_text = "\n".join(path.read_text(encoding="utf-8") for path in paths.logs_dir.glob("*.log"))
    assert daemon_client.token not in log_text
    assert local_secret_value not in log_text


def test_app_bootstrap_needs_model_and_is_redacted(daemon_client):
    response = daemon_client.client.get("/app/bootstrap", headers=daemon_client.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "needs_model"
    assert body["checks"]["model_config"] == "missing"
    assert body["runtime"]["configured"] is False
    text = response.text
    assert daemon_client.token not in text
    assert "api_key" not in text.lower()


def test_app_bootstrap_chat_ready_after_provider_save(daemon_client):
    secret = "placeholder-bootstrap-save-key"
    response = daemon_client.client.post(
        "/providers/save",
        headers=daemon_client.headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": secret},
    )
    assert response.status_code == 200

    bootstrap = daemon_client.client.get("/app/bootstrap", headers=daemon_client.headers)

    assert bootstrap.status_code == 200
    body = bootstrap.json()
    assert body["stage"] == "chat_ready"
    assert body["runtime"] == {"configured": True, "provider": "deepseek", "model": "deepseek-chat"}
    assert secret not in bootstrap.text
    assert daemon_client.token not in bootstrap.text
