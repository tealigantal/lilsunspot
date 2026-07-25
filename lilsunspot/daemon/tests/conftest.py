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
    import lilsunspot.daemon.audit as audit
    import lilsunspot.daemon.agent_host as agent_host
    import lilsunspot.daemon.agent_runner as agent_runner
    import lilsunspot.daemon.attachments as attachments
    import lilsunspot.daemon.capabilities as capabilities
    import lilsunspot.daemon.chat_client as chat_client
    import lilsunspot.daemon.config_paths as config_paths
    import lilsunspot.daemon.conversations as conversations
    import lilsunspot.daemon.delivery_actions as delivery_actions
    import lilsunspot.daemon.delivery_tools as delivery_tools
    import lilsunspot.daemon.doctor as doctor
    import lilsunspot.daemon.diagnostics as diagnostics
    import lilsunspot.daemon.gateway as gateway
    import lilsunspot.daemon.generation_controls as generation_controls
    import lilsunspot.daemon.hermes_compat as hermes_compat
    import lilsunspot.daemon.hermes_runtime as hermes_runtime
    import lilsunspot.daemon.logging_utils as logging_utils
    import lilsunspot.daemon.mode_intents as mode_intents
    import lilsunspot.daemon.mode_tools as mode_tools
    import lilsunspot.daemon.product_features as product_features
    import lilsunspot.daemon.modes as modes
    import lilsunspot.daemon.provider_client as provider_client
    import lilsunspot.daemon.providers as providers
    import lilsunspot.daemon.runtime_discovery as runtime_discovery
    import lilsunspot.daemon.safety as safety
    import lilsunspot.daemon.turn_coalescer as turn_coalescer
    import lilsunspot.daemon.weixin_runtime as weixin_runtime
    import lilsunspot.daemon.app as app_module

    config_paths = importlib.reload(config_paths)
    logging_utils = importlib.reload(logging_utils)
    auth = importlib.reload(auth)
    audit = importlib.reload(audit)
    conversations = importlib.reload(conversations)
    agent_host = importlib.reload(agent_host)
    agent_host.reset_for_tests()
    delivery_actions = importlib.reload(delivery_actions)
    delivery_tools = importlib.reload(delivery_tools)
    attachments = importlib.reload(attachments)
    capabilities = importlib.reload(capabilities)
    providers = importlib.reload(providers)
    provider_client = importlib.reload(provider_client)
    hermes_runtime = importlib.reload(hermes_runtime)
    runtime_discovery = importlib.reload(runtime_discovery)
    chat_client = importlib.reload(chat_client)
    modes = importlib.reload(modes)
    generation_controls = importlib.reload(generation_controls)
    mode_intents = importlib.reload(mode_intents)
    mode_tools = importlib.reload(mode_tools)
    agent_runner = importlib.reload(agent_runner)
    hermes_compat = importlib.reload(hermes_compat)
    gateway = importlib.reload(gateway)
    safety = importlib.reload(safety)
    turn_coalescer = importlib.reload(turn_coalescer)
    turn_coalescer.reset_for_tests()
    turn_coalescer.TEXT_BATCH_DELAY_SECONDS = 0.01
    weixin_runtime = importlib.reload(weixin_runtime)
    doctor = importlib.reload(doctor)
    diagnostics = importlib.reload(diagnostics)
    product_features = importlib.reload(product_features)
    app_module = importlib.reload(app_module)

    client = TestClient(app_module.app)
    token_file = config_paths.get_runtime_paths().token_file
    token = json.loads(token_file.read_text(encoding="utf-8"))["token"]
    headers = {auth.TOKEN_HEADER: token}
    return SimpleNamespace(
        app_module=app_module,
        agent_host=agent_host,
        agent_runner=agent_runner,
        audit=audit,
        auth=auth,
        attachments=attachments,
        capabilities=capabilities,
        chat_client=chat_client,
        client=client,
        config_paths=config_paths,
        conversations=conversations,
        delivery_actions=delivery_actions,
        delivery_tools=delivery_tools,
        headers=headers,
        gateway=gateway,
        generation_controls=generation_controls,
        hermes_compat=hermes_compat,
        hermes_runtime=hermes_runtime,
        diagnostics=diagnostics,
        modes=modes,
        mode_intents=mode_intents,
        mode_tools=mode_tools,
        product_features=product_features,
        token=token,
        turn_coalescer=turn_coalescer,
        weixin_runtime=weixin_runtime,
    )
