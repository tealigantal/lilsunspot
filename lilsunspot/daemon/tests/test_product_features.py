from __future__ import annotations


def test_product_feature_endpoints_require_token(daemon_client):
    response = daemon_client.client.get("/diagnostics/summary")

    assert response.status_code == 403
    assert daemon_client.client.get("/capability-graph").status_code == 403


def test_diagnostics_model_capabilities_and_feature_switches(daemon_client):
    client = daemon_client.client
    headers = daemon_client.headers

    diagnostics = client.get("/diagnostics/summary", headers=headers)
    assert diagnostics.status_code == 200
    body = diagnostics.json()
    assert "model" in body
    assert body["counts"]["capabilities"] >= 5
    assert body["upstream"]["available"] in {True, False}
    assert body["local_service"]["runtime_process"]["pid"]
    assert body["local_service"]["runtime_process"]["process_model"] in {
        "python_process",
        "pyinstaller_onedir_single_process",
        "pyinstaller_onefile_parent_child",
    }

    model = client.get("/providers/capabilities", headers=headers)
    assert model.status_code == 200
    assert model.json()["configured"] is False
    assert model.json()["capability_graph"]["by_id"]["chat.text"]["status"] == "needs_setup"
    assert model.json()["capability_graph"]["by_id"]["image.read"]["status"] == "needs_setup"
    assert any("还没有设置 AI 服务" in item for item in model.json()["limitations"])

    graph = client.get("/capability-graph", headers=headers)
    assert graph.status_code == 200
    graph_body = graph.json()
    assert graph_body["version"] == 1
    assert {"chat.text", "image.read", "file.read", "mode.adjust", "weixin.receive", "weixin.send_file"} <= set(
        graph_body["by_id"]
    )

    capabilities = client.get("/product/capabilities", headers=headers)
    assert capabilities.status_code == 200
    capability_ids = {item["id"] for item in capabilities.json()["capabilities"]}
    assert {"web_search", "file_read", "reminders", "weixin_send"} <= capability_ids

    toggled = client.patch("/product/capabilities/web_search", headers=headers, json={"enabled": True})
    assert toggled.status_code == 200
    assert toggled.json()["capability"]["enabled"] is True


def test_model_capabilities_distinguish_vision_backend_from_toolset(daemon_client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    backend_probe = {"called": False}

    def forbidden_backend_probe(*_args, **_kwargs):
        backend_probe["called"] = True
        raise AssertionError("external auxiliary backend probing must not run without explicit vision config")

    monkeypatch.setattr(daemon_client.chat_client, "_available_vision_backends", forbidden_backend_probe)
    monkeypatch.setattr(daemon_client.chat_client, "_resolve_hermes_vision_backend", forbidden_backend_probe)
    paths = daemon_client.config_paths.get_runtime_paths()
    deepseek_provider = {
        "id": "deepseek",
        "type": "cloud",
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "hermes_provider": "deepseek",
    }
    daemon_client.hermes_runtime.save_provider_credentials(
        deepseek_provider,
        "deepseek-chat",
        "placeholder-key",
        paths=paths,
    )

    response = daemon_client.client.get("/providers/capabilities", headers=daemon_client.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["supports_image"] is False
    assert body["main_supports_image"] is False
    assert body["auxiliary_configured"] is False
    assert body["image_backend"] == "none"
    assert body["image_input_mode"] == "text"
    assert body["image_capability_status"] == "needs_setup"
    assert body["capability_graph"]["by_id"]["image.read"]["blocking_reason"] == "capability.unsupported"
    assert any("辅助视觉" in item for item in body["limitations"])

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
    monkeypatch.setattr(daemon_client.chat_client, "_available_vision_backends", lambda paths=None: ["openrouter"])
    monkeypatch.setattr(
        daemon_client.chat_client,
        "_resolve_hermes_vision_backend",
        lambda paths=None, async_mode=False: ("openrouter", object(), "openai/gpt-4o-mini"),
    )

    response = daemon_client.client.get("/providers/capabilities", headers=daemon_client.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["supports_image"] is True
    assert body["main_supports_image"] is False
    assert body["auxiliary_configured"] is True
    assert body["image_backend"] == "auxiliary_vision"
    assert body["image_capability_status"] == "degraded"
    assert body["capability_graph"]["by_id"]["image.read"]["source"] == "auxiliary_vision"
    assert body["capability_graph"]["by_id"]["image.read"]["details"]["verification_status"] == "configured_not_verified"
    assert any("辅助视觉模型" in item for item in body["limitations"])

    clear_response = daemon_client.client.post(
        "/models/auxiliary",
        headers=daemon_client.headers,
        json={"task": "vision", "provider": "auto", "model": "", "base_url": "", "api_key": ""},
    )
    assert clear_response.status_code == 200
    backend_probe = {"called": False}

    def forbidden_backend_probe(*_args, **_kwargs):
        backend_probe["called"] = True
        raise AssertionError("external auxiliary backend probing must not run without explicit vision config")

    monkeypatch.setattr(daemon_client.chat_client, "_available_vision_backends", forbidden_backend_probe)
    monkeypatch.setattr(daemon_client.chat_client, "_resolve_hermes_vision_backend", forbidden_backend_probe)

    response = daemon_client.client.get("/providers/capabilities", headers=daemon_client.headers)
    body = response.json()
    assert body["supports_image"] is False
    assert body["auxiliary_configured"] is False
    assert body["image_backend"] == "none"


def test_model_capabilities_do_not_fetch_models_dev_on_cold_start(daemon_client, monkeypatch):
    import agent.models_dev as models_dev

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
        "placeholder-key",
        paths=paths,
    )
    backend_probe = {"called": False}

    def forbidden_backend_probe(*_args, **_kwargs):
        backend_probe["called"] = True
        raise AssertionError("external auxiliary backend probing must not run without explicit vision config")

    monkeypatch.setattr(daemon_client.chat_client, "_available_vision_backends", forbidden_backend_probe)
    monkeypatch.setattr(daemon_client.chat_client, "_resolve_hermes_vision_backend", forbidden_backend_probe)
    monkeypatch.setattr(models_dev, "_models_dev_cache", {})
    monkeypatch.setattr(models_dev, "_models_dev_cache_time", 0)
    monkeypatch.setattr(models_dev, "_disk_cache_age_seconds", lambda: None)
    monkeypatch.setattr(models_dev, "_load_disk_cache", lambda: {})
    called = {"fetch": False}

    def forbidden_fetch(*_args, **_kwargs):
        called["fetch"] = True
        raise AssertionError("models.dev network fetch must not run during capability status reads")

    monkeypatch.setattr(models_dev, "fetch_models_dev", forbidden_fetch)

    response = daemon_client.client.get("/providers/capabilities", headers=daemon_client.headers)

    assert response.status_code == 200
    body = response.json()
    assert called["fetch"] is False
    assert backend_probe["called"] is False
    assert body["configured"] is True
    assert body["main_supports_image"] is False
    assert body["image_input_mode"] == "text"
    assert body["capability_graph"]["by_id"]["image.read"]["status"] == "needs_setup"


def test_upstream_status_sums_category_changed_files(daemon_client, tmp_path, monkeypatch):
    product_features = daemon_client.product_features
    reports_dir = tmp_path / "lilsunspot" / "notes" / "upstream-sync-reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "2026-06-11-test.md").write_text(
        "\n".join(
            [
                "# Hermes upstream check report",
                "",
                "Generated: 2026-06-11 20:32:15 +08:00",
                "",
                "- Working tree dirty: True",
                "- Upstream commits since comparison base: 9",
                "",
                "| Category | Changed files |",
                "| --- | ---: |",
                "| Other upstream | 12 |",
                "| Tools | 3 |",
                "",
                "## Capability surface gaps",
                "",
                "- Missing TOOLSETS in current worktree: `context_engine`",
                "- Missing CONFIGURABLE_TOOLSETS in current worktree: `context_engine`",
                "- Missing /capabilities mappings: `context_engine`",
                "- Missing DEFAULT_CONFIG keys in current worktree: `gateway`, `tools`, `paste_collapse_threshold`",
                "- Missing DEFAULT_CONFIG capability mappings: `gateway`, `tools`, `paste_collapse_threshold`",
                "",
                "## Changed files sample",
                "- `sample.py`",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(product_features, "_repo_root", lambda: tmp_path)

    status = product_features.upstream_status()

    assert status["available"] is True
    assert status["commits_since_base"] == 9
    assert status["changed_files"] == 15
    assert status["working_tree_dirty"] is True
    assert status["missing_toolsets"] == ["context_engine"]
    assert status["missing_configurable_toolsets"] == ["context_engine"]
    assert status["missing_capability_mappings"] == ["context_engine"]
    assert status["missing_default_config_keys"] == ["gateway", "tools", "paste_collapse_threshold"]
    assert status["missing_config_mappings"] == ["gateway", "tools", "paste_collapse_threshold"]


def test_conversation_search_finds_messages_and_attachments(daemon_client):
    conversations = daemon_client.conversations
    paths = daemon_client.config_paths.get_runtime_paths()
    client = daemon_client.client
    headers = daemon_client.headers

    message = conversations.create_message(
        conversation_id="personal",
        source="desktop",
        role="user",
        text="请帮我查找季度预算材料",
        paths=paths,
    )
    conversations.create_attachment_record(
        message_id=message["id"],
        conversation_id="personal",
        safe_path=paths.data_dir / "attachments" / "budget.txt",
        file_name="budget.txt",
        mime_type="text/plain",
        size_bytes=12,
        summary_status="ready",
        summary_text="季度预算附件摘要",
        paths=paths,
    )

    message_search = client.post(
        "/conversations/search",
        headers=headers,
        json={"query": "季度预算", "limit": 10},
    )
    assert message_search.status_code == 200
    assert any(item["type"] == "message" for item in message_search.json()["results"])

    attachment_search = client.post(
        "/conversations/search",
        headers=headers,
        json={"query": "附件摘要", "limit": 10},
    )
    assert attachment_search.status_code == 200
    assert any(item["type"] == "attachment" for item in attachment_search.json()["results"])


def test_reminders_and_memory_are_persistent_product_records(daemon_client):
    client = daemon_client.client
    headers = daemon_client.headers

    created_reminder = client.post(
        "/reminders",
        headers=headers,
        json={"title": "明早看日报", "prompt": "提醒我看日报", "due_at": "明天 09:00"},
    )
    assert created_reminder.status_code == 200
    reminder = created_reminder.json()["reminder"]
    assert reminder["enabled"] is True

    reminder_list = client.get("/reminders", headers=headers)
    assert reminder_list.status_code == 200
    assert reminder["id"] in {item["id"] for item in reminder_list.json()["reminders"]}

    completed = client.patch(f"/reminders/{reminder['id']}", headers=headers, json={"completed": True})
    assert completed.status_code == 200
    assert completed.json()["reminder"]["enabled"] is False
    assert completed.json()["reminder"]["completed_at"]

    created_memory = client.post(
        "/memory",
        headers=headers,
        json={"text": "我喜欢简短回复", "source": "manual"},
    )
    assert created_memory.status_code == 200
    memory = created_memory.json()["memory"]
    assert memory["enabled"] is True

    disabled = client.patch(f"/memory/{memory['id']}", headers=headers, json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["memory"]["enabled"] is False

    deleted = client.delete(f"/memory/{memory['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
