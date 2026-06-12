from __future__ import annotations

import json


def test_capabilities_list_covers_hermes_toolsets_and_runtime_surfaces(daemon_client):
    response = daemon_client.client.get("/capabilities", headers=daemon_client.headers)
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["capabilities"]}

    from hermes_cli.tools_config import CONFIGURABLE_TOOLSETS
    from toolsets import TOOLSETS

    for toolset, _label, _description in CONFIGURABLE_TOOLSETS:
        assert f"toolset.{toolset}" in ids

    for toolset in TOOLSETS:
        assert f"toolset.{toolset}" in ids

    assert "model.main" in ids
    assert "model.fallbacks" in ids
    assert "integration.mcp_servers" in ids
    assert "security.audit" in ids
    assert "runtime.upstream_sync" in ids
    assert body["platform"] == "lilsunspot"
    hermes_weixin = next(item for item in body["capabilities"] if item["id"] == "toolset.hermes-weixin")
    assert hermes_weixin["configurable"] is False


def test_capability_toggle_writes_lilsunspot_platform_toolsets(daemon_client):
    response = daemon_client.client.patch(
        "/capabilities/toolset.terminal",
        headers=daemon_client.headers,
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["capability"]["enabled"] is True

    config = daemon_client.hermes_runtime.read_hermes_config(daemon_client.config_paths.get_runtime_paths())
    assert "terminal" in config["platform_toolsets"]["lilsunspot"]

    agent_toolsets = daemon_client.capabilities.enabled_toolsets_for_agent(daemon_client.config_paths.get_runtime_paths())
    assert "terminal" in agent_toolsets


def test_models_runtime_fallback_auxiliary_and_mcp_roundtrip_are_redacted(daemon_client):
    fallback_response = daemon_client.client.post(
        "/models/fallbacks",
        headers=daemon_client.headers,
        json={"fallbacks": [{"provider": "openrouter", "model": "openai/gpt-4o-mini"}]},
    )
    assert fallback_response.status_code == 200
    assert fallback_response.json()["models"]["fallback_providers"][0]["provider"] == "openrouter"

    auxiliary_response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={"task": "vision", "provider": "openrouter", "model": "openai/gpt-4o-mini"},
    )
    assert auxiliary_response.status_code == 200
    assert auxiliary_response.json()["models"]["auxiliary"]["vision"]["provider"] == "openrouter"

    mcp_response = daemon_client.client.post(
        "/mcp/servers",
        headers=daemon_client.headers,
        json={
            "name": "local_test",
            "config": {
                "command": "npx",
                "args": ["-y", "example", "--token", "inline-secret-value"],
                "env": {"API_TOKEN": "secret-token-value"},
                "headers": {"Authorization": "Bearer header-secret-value"},
            },
        },
    )
    assert mcp_response.status_code == 200
    servers = mcp_response.json()["servers"]
    assert servers["local_test"]["env"]["API_TOKEN"] == "[已隐藏]"
    response_text = json.dumps(mcp_response.json(), ensure_ascii=False)
    assert "inline-secret-value" not in response_text
    assert "header-secret-value" not in response_text

    config = daemon_client.hermes_runtime.read_hermes_config(daemon_client.config_paths.get_runtime_paths())
    assert config["mcp_servers"]["local_test"]["env"]["API_TOKEN"] == "secret-token-value"
    assert "inline-secret-value" in config["mcp_servers"]["local_test"]["args"]


def test_safety_audit_and_diagnostics_export_are_redacted(daemon_client):
    approval = daemon_client.client.post(
        "/safety/approvals/request",
        headers=daemon_client.headers,
        json={
            "operation": "shell",
            "summary": "运行需要确认的命令",
            "details": {"api_key": "secret-key-value", "command": "echo safe"},
            "source": "test",
        },
    )
    assert approval.status_code == 200

    audit_response = daemon_client.client.get("/safety/audit", headers=daemon_client.headers)
    assert audit_response.status_code == 200
    audit_text = json.dumps(audit_response.json(), ensure_ascii=False)
    assert "secret-key-value" not in audit_text
    assert "[已隐藏]" in audit_text

    export_response = daemon_client.client.post("/doctor/diagnostics/export", headers=daemon_client.headers)
    assert export_response.status_code == 200
    export_body = export_response.json()
    assert export_body["ok"] is True
    assert export_body["file_name"].endswith(".zip")
    diagnostics_dir = daemon_client.config_paths.get_runtime_paths().data_dir / "diagnostics"
    assert (diagnostics_dir / export_body["file_name"]).exists()
