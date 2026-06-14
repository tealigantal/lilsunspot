from __future__ import annotations

import asyncio
import json


def test_capabilities_list_covers_hermes_toolsets_and_runtime_surfaces(daemon_client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_BASE_URL", "")

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
    vision = next(item for item in body["capabilities"] if item["id"] == "toolset.vision")
    assert vision["status"] == "blocked"
    assert any("Hermes vision backend" in item for item in vision["dependencies"])
    assert vision["enabled"] is True
    desktop_upload = next(item for item in body["capabilities"] if item["id"] == "runtime.desktop_image_upload")
    assert desktop_upload["status"] == "enabled"
    assert desktop_upload["available"] is True

    snapshot = daemon_client.capabilities.capability_prompt_snapshot(daemon_client.config_paths.get_runtime_paths())
    assert "当前 lilsunspot 能力状态快照" in snapshot
    assert "runtime.desktop_image_upload / 桌面聊天图片上传: status=enabled" in snapshot
    assert "toolset.vision / 图片理解" in snapshot


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
        json={
            "task": "vision",
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "api_key": "placeholder-openrouter-value",
        },
    )
    assert auxiliary_response.status_code == 200
    assert auxiliary_response.json()["models"]["auxiliary"]["vision"]["provider"] == "openrouter"
    assert auxiliary_response.json()["models"]["lilsunspot_auxiliary"]["vision"]["provider"] == "openrouter"
    assert "placeholder-openrouter-value" not in str(auxiliary_response.json())

    openai_auxiliary_response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={
            "task": "vision",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "api_key": "placeholder-openai-value",
        },
    )
    assert openai_auxiliary_response.status_code == 200
    openai_models = openai_auxiliary_response.json()["models"]
    assert openai_models["auxiliary"]["vision"]["provider"] == "custom"
    assert openai_models["auxiliary"]["vision"]["base_url"] == "https://api.openai.com/v1"
    assert openai_models["lilsunspot_auxiliary"]["vision"]["provider"] == "openai"
    assert "placeholder-openai-value" not in str(openai_auxiliary_response.json())

    saved_main = daemon_client.client.post(
        "/providers/save",
        headers=daemon_client.headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": "placeholder-deepseek-value"},
    )
    assert saved_main.status_code == 200
    models_after_main_save = daemon_client.client.get("/models/runtime", headers=daemon_client.headers).json()
    assert models_after_main_save["lilsunspot_auxiliary"]["vision"]["provider"] == "openai"
    assert "placeholder-deepseek-value" not in str(saved_main.json())

    clear_auxiliary_response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={"task": "vision", "provider": "auto", "model": ""},
    )
    assert clear_auxiliary_response.status_code == 200
    cleared_models = clear_auxiliary_response.json()["models"]
    assert "vision" not in cleared_models["auxiliary"]
    assert "vision" not in cleared_models["lilsunspot_auxiliary"]

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


def test_qwen_auxiliary_writes_mainland_dashscope_base_url_and_migrates_old_config(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={
            "task": "vision",
            "provider": "qwen",
            "model": "qwen-vl-max",
            "api_key": "placeholder-dashscope-value",
        },
    )

    assert response.status_code == 200
    models = response.json()["models"]
    assert models["auxiliary"]["vision"]["provider"] == "alibaba"
    assert models["auxiliary"]["vision"]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert models["lilsunspot_auxiliary"]["vision"]["provider"] == "qwen"
    assert models["lilsunspot_auxiliary"]["vision"]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert "placeholder-dashscope-value" not in json.dumps(models, ensure_ascii=False)

    daemon_client.hermes_runtime.write_hermes_config(
        {
            "auxiliary": {"vision": {"provider": "alibaba", "model": "qwen-vl-max"}},
            "lilsunspot": {
                "auxiliary": {
                    "vision": {
                        "provider": "qwen",
                        "model": "qwen-vl-max",
                        "base_url": "",
                    }
                }
            },
        },
        paths,
    )

    migrated = daemon_client.hermes_runtime.read_hermes_config(paths)
    assert migrated["auxiliary"]["vision"]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert migrated["lilsunspot"]["auxiliary"]["vision"]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_models_auxiliary_requires_key_for_first_cloud_provider(daemon_client):
    response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={"task": "vision", "provider": "openrouter", "model": "openai/gpt-4o-mini"},
    )

    assert response.status_code == 400
    assert "API Key" in response.json()["detail"]


def test_provider_save_reuses_existing_key_when_reconfiguring_model(daemon_client):
    paths = daemon_client.config_paths.get_runtime_paths()
    first = daemon_client.client.post(
        "/providers/save",
        headers=daemon_client.headers,
        json={"provider": "deepseek", "model": "deepseek-chat", "api_key": "placeholder-deepseek-value"},
    )
    assert first.status_code == 200

    second = daemon_client.client.post(
        "/providers/save",
        headers=daemon_client.headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-reasoner",
            "api_key": "",
            "base_url_override": "https://api.deepseek.com/v1",
        },
    )

    assert second.status_code == 200
    assert second.json()["model"] == "deepseek-reasoner"
    env_text = (paths.hermes_home / ".env").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=placeholder-deepseek-value" in env_text
    assert "placeholder-deepseek-value" not in json.dumps(second.json(), ensure_ascii=False)


def test_models_auxiliary_rejects_user_misclicks_without_writing_config(daemon_client):
    missing_provider = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={"task": "vision", "provider": "auto", "model": "qwen-vl-max"},
    )
    assert missing_provider.status_code == 400
    assert "选择图片识别服务" in missing_provider.json()["detail"]

    missing_model = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={
            "task": "vision",
            "provider": "ollama",
            "model": " ",
            "base_url": "http://127.0.0.1:11434/v1",
        },
    )
    assert missing_model.status_code == 400
    assert "视觉模型名称" in missing_model.json()["detail"]

    models = daemon_client.client.get("/models/runtime", headers=daemon_client.headers).json()
    assert "vision" not in models["auxiliary"]
    assert "vision" not in models["lilsunspot_auxiliary"]


def test_describe_image_uses_auxiliary_vision_when_main_model_is_text_only(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    daemon_client.hermes_runtime.save_provider_credentials(
        {
            "id": "deepseek",
            "type": "cloud",
            "env_key": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "hermes_provider": "deepseek",
        },
        "deepseek-chat",
        "placeholder-deepseek-value",
        paths=paths,
    )
    auxiliary_response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={
            "task": "vision",
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "api_key": "placeholder-openrouter-value",
        },
    )
    assert auxiliary_response.status_code == 200
    seen: dict[str, object] = {}

    def fake_resolver(paths=None, async_mode=False):
        seen["resolver_async"] = async_mode
        return "openrouter", object(), "openai/gpt-4o-mini"

    async def fake_vision_call(messages):
        content = messages[-1]["content"]
        assert isinstance(content, list)
        assert any(item.get("type") == "image_url" for item in content if isinstance(item, dict))
        seen["messages"] = messages
        return {"choices": [{"message": {"content": "画面里是一张测试图片。"}}]}

    monkeypatch.setattr(daemon_client.chat_client, "_available_vision_backends", lambda paths=None: ["openrouter"])
    monkeypatch.setattr(daemon_client.chat_client, "_resolve_hermes_vision_backend", fake_resolver)
    monkeypatch.setattr(daemon_client.chat_client, "_call_hermes_vision", fake_vision_call)

    result = asyncio.run(
        daemon_client.chat_client.describe_image_data_url(
            "data:image/png;base64,iVBORw0KGgo=",
            file_name="unit.png",
            paths=paths,
        )
    )

    assert result["ok"] is True
    assert result["summary"] == "画面里是一张测试图片。"
    assert result["backend"] == "auxiliary_vision"
    assert result["stage"] == "vision.auxiliary"
    assert result["provider"] == "openrouter"
    assert result["model"] == "openai/gpt-4o-mini"
    assert seen["resolver_async"] is False
    capabilities = daemon_client.client.get("/providers/capabilities", headers=daemon_client.headers).json()
    image_node = capabilities["capability_graph"]["by_id"]["image.read"]
    assert image_node["status"] == "ready"
    assert image_node["details"]["verification_status"] == "verified"


def test_describe_image_auxiliary_errors_are_explainable_and_redacted(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    daemon_client.hermes_runtime.save_provider_credentials(
        {
            "id": "deepseek",
            "type": "cloud",
            "env_key": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "hermes_provider": "deepseek",
        },
        "deepseek-chat",
        "placeholder-deepseek-value",
        paths=paths,
    )
    auxiliary_response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={
            "task": "vision",
            "provider": "openrouter",
            "model": "missing-vision-model",
            "api_key": "placeholder-openrouter-value",
        },
    )
    assert auxiliary_response.status_code == 200

    def fake_resolver(paths=None, async_mode=False):
        return "openrouter", object(), "missing-vision-model"

    async def fake_vision_call(_messages):
        error = RuntimeError("model not found")
        setattr(error, "status_code", 404)
        raise error

    monkeypatch.setattr(daemon_client.chat_client, "_available_vision_backends", lambda paths=None: ["openrouter"])
    monkeypatch.setattr(daemon_client.chat_client, "_resolve_hermes_vision_backend", fake_resolver)
    monkeypatch.setattr(daemon_client.chat_client, "_call_hermes_vision", fake_vision_call)

    result = asyncio.run(
        daemon_client.chat_client.describe_image_data_url(
            "data:image/png;base64,iVBORw0KGgo=",
            file_name="unit.png",
            paths=paths,
        )
    )

    assert result["ok"] is False
    assert result["backend"] == "auxiliary_vision"
    assert result["stage"] == "vision.auxiliary"
    assert result["error_code"] == "model_not_found"
    assert "模型" in result["message"]
    assert "placeholder-openrouter-value" not in json.dumps(result, ensure_ascii=False)
    capabilities = daemon_client.client.get("/providers/capabilities", headers=daemon_client.headers).json()
    image_node = capabilities["capability_graph"]["by_id"]["image.read"]
    assert image_node["status"] == "blocked"
    assert image_node["details"]["verification_status"] == "failed"
    assert image_node["details"]["last_error_code"] == "model_not_found"


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
