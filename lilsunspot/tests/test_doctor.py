def test_doctor_run_returns_structured_checks(daemon_client, auth_headers):
    response = daemon_client.client.get("/doctor/run", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "checks" in body
    assert isinstance(body["checks"], list)
    assert body["checks"]

    by_id = {check["id"]: check for check in body["checks"]}
    assert by_id["data_dir_exists"]["ok"] is True
    assert by_id["hermes_home_exists"]["ok"] is True
    assert by_id["logs_dir_exists"]["ok"] is True
    assert by_id["runtime_token_exists"]["ok"] is True
    assert by_id["resource:provider_registry.yaml"]["ok"] is True
    assert by_id["resource:default_mode_profiles.yaml"]["ok"] is True
    assert by_id["resource:default_safety_policy.yaml"]["ok"] is True
    assert {"id", "ok", "severity", "message"} <= set(body["checks"][0])


def test_doctor_reports_saved_provider_and_key(daemon_client, auth_headers):
    daemon_client.client.post(
        "/providers/save",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "test-key-redacted-doctor",
        },
    )

    response = daemon_client.client.post("/doctor/run", headers=auth_headers)

    assert response.status_code == 200
    by_id = {check["id"]: check for check in response.json()["checks"]}
    assert by_id["hermes_env_exists"]["ok"] is True
    assert by_id["hermes_config_parseable"]["ok"] is True
    assert by_id["current_provider_configured"]["ok"] is True
    assert by_id["current_provider_key_configured"]["ok"] is True
