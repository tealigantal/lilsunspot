from __future__ import annotations

import importlib
import json
import re
import shutil
import sys
from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    if sys.platform == "win32" and getattr(config, "_env_timeout_method", None) == "signal":
        config._env_timeout_method = "thread"


@pytest.fixture()
def tmp_path(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)[:80]
    base = (Path.cwd() / ".pytest_cache" / "lilsunspot-tmp").resolve()
    path = (base / f"{safe_name}-{uuid4().hex}").resolve()
    if not str(path).startswith(str(base)):
        raise RuntimeError("Refusing to create a temporary path outside the lilsunspot test base.")
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists() and str(path).startswith(str(base)):
            shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def daemon_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(tmp_path / "data"))

    import lilsunspot.daemon.config_paths as config_paths
    import lilsunspot.daemon.logging_utils as logging_utils
    import lilsunspot.daemon.auth as auth
    import lilsunspot.daemon.providers as providers
    import lilsunspot.daemon.hermes_runtime as hermes_runtime
    import lilsunspot.daemon.app as app_module

    importlib.reload(config_paths)
    importlib.reload(logging_utils)
    importlib.reload(auth)
    importlib.reload(providers)
    importlib.reload(hermes_runtime)
    app_module = importlib.reload(app_module)

    paths = config_paths.get_runtime_paths()
    token = json.loads(paths.token_file.read_text(encoding="utf-8"))["token"]
    return SimpleNamespace(
        client=TestClient(app_module.app),
        token=token,
        paths=paths,
        token_header=auth.TOKEN_HEADER,
        app_module=app_module,
        providers_module=providers,
    )


@pytest.fixture()
def auth_headers(daemon_client):
    return {daemon_client.token_header: daemon_client.token}
