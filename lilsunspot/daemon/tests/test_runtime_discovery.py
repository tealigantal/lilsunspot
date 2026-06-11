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
    assert payload["process"]["pid"] == payload["pid"]
    assert isinstance(payload["process"]["parent_pid"], int)
    assert payload["process"]["process_model"] in {
        "python_process",
        "pyinstaller_onedir_single_process",
        "pyinstaller_onefile_parent_child",
    }
    assert "token" not in json.dumps(payload["process"], ensure_ascii=False)
    assert "token" not in payload
    assert daemon_client.token not in json.dumps(payload, ensure_ascii=False)

    runtime = daemon_client.client.get("/runtime/info", headers=daemon_client.headers)
    assert runtime.status_code == 200
    assert runtime.json()["runtime_file"] == str(paths.runtime_file)
    assert runtime.json()["process"]["pid"] == payload["pid"]


def test_runtime_discovery_rejects_non_localhost_binding():
    from lilsunspot.daemon.runtime_discovery import base_url_for

    with pytest.raises(ValueError, match="127.0.0.1"):
        base_url_for("0.0.0.0", 8765)


def test_launcher_health_url_uses_health_endpoint():
    from lilsunspot.daemon.launcher import health_url

    assert health_url("http://127.0.0.1:8765/") == "http://127.0.0.1:8765/health"


def test_daemon_file_lock_is_exclusive(tmp_path):
    from lilsunspot.daemon.launcher import DaemonFileLock

    lock_path = tmp_path / "data" / "lilsunspotd.lock"
    first = DaemonFileLock(lock_path)
    second = DaemonFileLock(lock_path)

    assert first.acquire(blocking=False) is True
    assert second.acquire(blocking=False) is False
    first.release()
    assert second.acquire(blocking=False) is True
    second.release()


def test_launcher_reuses_existing_health_without_rewriting_descriptor(tmp_path, monkeypatch):
    import lilsunspot.daemon.launcher as launcher

    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(launcher, "wait_for_health", lambda base_url, timeout_seconds=10.0: True)
    monkeypatch.setattr(launcher, "daemon_lock_path", lambda paths=None: (_ for _ in ()).throw(AssertionError("lock not needed")))

    launcher.run_server()
