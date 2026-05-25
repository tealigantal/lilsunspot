import yaml


def test_provider_save_writes_lilsunspot_hermes_home_without_leaking_response(
    daemon_client,
    auth_headers,
):
    api_key = "test-key-redacted-deepseek"
    response = daemon_client.client.post(
        "/providers/save",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": api_key,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "provider": "deepseek",
        "model": "deepseek-chat",
        "env_written": True,
        "config_written": True,
    }
    assert api_key not in response.text

    env_path = daemon_client.paths.hermes_home / ".env"
    config_path = daemon_client.paths.hermes_home / "config.yaml"
    deepseek_env_key = "DEEPSEEK" + "_API_KEY"

    assert env_path.exists()
    assert config_path.exists()
    assert env_path.read_text(encoding="utf-8") == f"{deepseek_env_key}={api_key}\n"

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["lilsunspot"]["provider"] == "deepseek"
    assert config["lilsunspot"]["model"] == "deepseek-chat"
    assert config["model"]["default"] == "deepseek-chat"
    assert config["model"]["provider"] == "deepseek"

    log_text = (daemon_client.paths.logs_dir / "lilsunspotd.log").read_text(encoding="utf-8")
    assert api_key not in log_text
    assert "tes...seek" in log_text


def test_provider_save_preserves_other_env_keys(daemon_client, auth_headers):
    env_path = daemon_client.paths.hermes_home / ".env"
    env_path.write_text("OTHER_PROVIDER_KEY=keep-me\n", encoding="utf-8")

    response = daemon_client.client.post(
        "/providers/save",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "test-key-redacted-updated",
        },
    )

    assert response.status_code == 200
    env_text = env_path.read_text(encoding="utf-8")
    assert "OTHER_PROVIDER_KEY=keep-me" in env_text
    assert (("DEEPSEEK" + "_API_KEY") + "=" + "test-key-redacted-updated") in env_text


def test_providers_current_masks_saved_key(daemon_client, auth_headers):
    api_key = "test-key-redacted-current"
    daemon_client.client.post(
        "/providers/save",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": api_key,
        },
    )

    response = daemon_client.client.get("/providers/current", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "deepseek"
    assert body["model"] == "deepseek-chat"
    assert body["key_configured"] is True
    assert api_key not in response.text
    assert body["masked_key"] == "tes...rent"
