from __future__ import annotations

import json

import pytest


def test_daemon_writes_runtime_descriptor_without_token_value(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    payload = json.loads(paths.runtime_file.read_text(encoding="utf-8"))

    assert payload["type"] == "lilsunspot-daemon-runtime"
    assert payload["version"] == 1
    assert payload["base_url"] == "http://127.0.0.1:8765"
    assert payload["host"] == "127.0.0.1"
    assert payload["port"] == 8765
    assert payload["token_file"] == str(paths.token_file)
    assert "token" not in payload
    assert daemon_client.token not in json.dumps(payload, ensure_ascii=False)

    runtime = daemon_client.client.get("/runtime/info", headers=daemon_client.headers)
    assert runtime.status_code == 200
    assert runtime.json()["runtime_file"] == str(paths.runtime_file)


def test_runtime_discovery_rejects_non_localhost_binding():
    from lilsunspot.daemon.runtime_discovery import base_url_for

    with pytest.raises(ValueError, match="127.0.0.1"):
        base_url_for("0.0.0.0", 8765)


def test_launcher_health_url_uses_health_endpoint():
    from lilsunspot.daemon.launcher import health_url

    assert health_url("http://127.0.0.1:8765/") == "http://127.0.0.1:8765/health"
