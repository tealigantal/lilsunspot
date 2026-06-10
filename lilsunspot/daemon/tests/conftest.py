from __future__ import annotations

import importlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def daemon_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(tmp_path / "data"))

    import lilsunspot.daemon.auth as auth
    import lilsunspot.daemon.agent_runner as agent_runner
    import lilsunspot.daemon.attachments as attachments
    import lilsunspot.daemon.chat_client as chat_client
    import lilsunspot.daemon.config_paths as config_paths
    import lilsunspot.daemon.conversations as conversations
    import lilsunspot.daemon.doctor as doctor
    import lilsunspot.daemon.gateway as gateway
    import lilsunspot.daemon.hermes_compat as hermes_compat
    import lilsunspot.daemon.hermes_runtime as hermes_runtime
    import lilsunspot.daemon.logging_utils as logging_utils
    import lilsunspot.daemon.mode_intents as mode_intents
    import lilsunspot.daemon.modes as modes
    import lilsunspot.daemon.provider_client as provider_client
    import lilsunspot.daemon.providers as providers
    import lilsunspot.daemon.runtime_discovery as runtime_discovery
    import lilsunspot.daemon.safety as safety
    import lilsunspot.daemon.weixin_runtime as weixin_runtime
    import lilsunspot.daemon.app as app_module

    config_paths = importlib.reload(config_paths)
    logging_utils = importlib.reload(logging_utils)
    auth = importlib.reload(auth)
    conversations = importlib.reload(conversations)
    agent_runner = importlib.reload(agent_runner)
    attachments = importlib.reload(attachments)
    providers = importlib.reload(providers)
    provider_client = importlib.reload(provider_client)
    hermes_runtime = importlib.reload(hermes_runtime)
    runtime_discovery = importlib.reload(runtime_discovery)
    chat_client = importlib.reload(chat_client)
    modes = importlib.reload(modes)
    mode_intents = importlib.reload(mode_intents)
    hermes_compat = importlib.reload(hermes_compat)
    gateway = importlib.reload(gateway)
    safety = importlib.reload(safety)
    weixin_runtime = importlib.reload(weixin_runtime)
    doctor = importlib.reload(doctor)
    app_module = importlib.reload(app_module)

    client = TestClient(app_module.app)
    token_file = config_paths.get_runtime_paths().token_file
    token = json.loads(token_file.read_text(encoding="utf-8"))["token"]
    headers = {auth.TOKEN_HEADER: token}
    return SimpleNamespace(
        app_module=app_module,
        agent_runner=agent_runner,
        auth=auth,
        attachments=attachments,
        chat_client=chat_client,
        client=client,
        config_paths=config_paths,
        conversations=conversations,
        headers=headers,
        hermes_compat=hermes_compat,
        hermes_runtime=hermes_runtime,
        mode_intents=mode_intents,
        token=token,
        weixin_runtime=weixin_runtime,
    )
