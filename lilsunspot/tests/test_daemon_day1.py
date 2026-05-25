import importlib
import json

from fastapi.testclient import TestClient


def test_day1_daemon_health_token_protection_and_doctor(tmp_path, monkeypatch):
    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(tmp_path / "data"))

    import lilsunspot.daemon.config_paths as config_paths
    import lilsunspot.daemon.auth as auth
    import lilsunspot.daemon.app as app_module

    importlib.reload(config_paths)
    importlib.reload(auth)
    app_module = importlib.reload(app_module)

    client = TestClient(app_module.app)

    assert client.get("/health").json() == {"ok": True}
    assert client.get("/providers").status_code == 403

    token_file = config_paths.get_runtime_paths().token_file
    token = json.loads(token_file.read_text(encoding="utf-8"))["token"]

    providers_response = client.get(
        "/providers",
        headers={auth.TOKEN_HEADER: token},
    )
    assert providers_response.status_code == 200
    assert len(providers_response.json()["providers"]) >= 6

    doctor_response = client.get(
        "/doctor/run",
        headers={auth.TOKEN_HEADER: token},
    )
    assert doctor_response.status_code == 200
    assert doctor_response.json()["ok"] is True

    test_secret = "DAY1_TEST_TOKEN_VALUE"
    save_response = client.post(
        "/providers/save",
        headers={auth.TOKEN_HEADER: token},
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": test_secret},
    )
    assert save_response.status_code == 200
    env_text = (config_paths.get_runtime_paths().hermes_home / ".env").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" in env_text
    assert test_secret in env_text
