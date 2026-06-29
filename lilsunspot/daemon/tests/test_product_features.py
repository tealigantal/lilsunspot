from __future__ import annotations

from datetime import datetime, timedelta, timezone


def test_product_feature_endpoints_require_token(daemon_client):
    response = daemon_client.client.get("/diagnostics/summary")

    assert response.status_code == 403
    assert daemon_client.client.get("/capability-graph").status_code == 403
    assert daemon_client.client.get("/ui/overview").status_code == 403
    assert daemon_client.client.get("/tasks").status_code == 403
    assert daemon_client.client.get("/profiles").status_code == 403
    assert daemon_client.client.get("/usage/summary").status_code == 403
    assert daemon_client.client.get("/advanced/extensions").status_code == 403
    assert daemon_client.client.get("/advanced/config/export").status_code == 403
    assert daemon_client.client.post("/advanced/config/import", json={"config": {}}).status_code == 403


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


def test_tasks_profiles_usage_and_overview_are_product_wrappers(daemon_client):
    client = daemon_client.client
    headers = daemon_client.headers
    due_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="minutes")

    created = client.post(
        "/tasks",
        headers=headers,
        json={"title": "明早看日报", "prompt": "提醒我看日报", "due_at": due_at, "kind": "reminder", "schedule": "daily"},
    )
    assert created.status_code == 200
    task = created.json()["task"]
    assert task["status"] == "active"
    assert task["next_run_at"]
    assert task["schedule"] == "daily"
    assert task["metadata"]["scheduler"] == "background"

    paused = client.patch(f"/tasks/{task['id']}", headers=headers, json={"enabled": False})
    assert paused.status_code == 200
    assert paused.json()["task"]["status"] == "paused"

    run = client.post(f"/tasks/{task['id']}/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["task"]["last_run_at"]
    assert run.json()["run"]["state"] == "succeeded"
    assert run.json()["run"]["message_id"]

    listed = client.get("/tasks", headers=headers)
    assert listed.status_code == 200
    assert task["id"] in {item["id"] for item in listed.json()["tasks"]}

    profile = client.post(
        "/profiles",
        headers=headers,
        json={"name": "工作助理", "instructions": "先给结论，再给步骤。"},
    )
    assert profile.status_code == 200
    profile_id = profile.json()["profile"]["id"]
    assert client.get("/profiles", headers=headers).json()["profiles"][0]["id"] == profile_id

    usage = client.get("/usage/summary", headers=headers)
    assert usage.status_code == 200
    assert usage.json()["tasks"]["total"] >= 1
    assert usage.json()["costs"]["available"] is False

    overview = client.get("/ui/overview", headers=headers)
    assert overview.status_code == 200
    assert "diagnostics" in overview.json()
    assert overview.json()["tasks"]["total"] >= 1

    advanced = client.get("/advanced/extensions", headers=headers)
    assert advanced.status_code == 200
    assert advanced.json()["mode"] == "guarded"
    assert advanced.json()["safe_actions"]["config_export"] is True
    assert advanced.json()["dangerous_actions_enabled"] is False

    deleted = client.delete(f"/profiles/{profile_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_product_task_scheduler_runs_due_tasks_and_reschedules_daily(daemon_client):
    product_features = daemon_client.product_features
    conversations = daemon_client.conversations
    paths = daemon_client.config_paths.get_runtime_paths()
    now = datetime.now(timezone.utc)
    once = product_features.create_task(
        title="到点提醒",
        prompt="提醒我喝水",
        due_at=(now - timedelta(minutes=1)).isoformat(timespec="minutes"),
        kind="reminder",
        schedule="once",
        paths=paths,
    )
    daily = product_features.create_task(
        title="每日检查",
        prompt="检查本地状态",
        due_at=(now - timedelta(days=1)).isoformat(timespec="minutes"),
        kind="check",
        schedule="daily",
        paths=paths,
    )

    results = product_features.run_due_tasks(paths=paths, now=now)

    result_by_id = {item["task"]["id"]: item for item in results}
    assert once["id"] in result_by_id
    assert daily["id"] in result_by_id
    assert result_by_id[once["id"]]["task"]["status"] == "completed"
    assert result_by_id[daily["id"]]["task"]["status"] == "active"
    assert result_by_id[daily["id"]]["task"]["next_run_at"]
    assert result_by_id[daily["id"]]["task"]["due_at"] != daily["due_at"]
    messages = conversations.list_messages("personal", limit=20, paths=paths)
    assert any("任务提醒：到点提醒" in item["text"] for item in messages)
    assert any("定时检查：每日检查" in item["text"] for item in messages)


def test_advanced_config_export_import_is_redacted_and_product_scoped(daemon_client):
    product_features = daemon_client.product_features
    hermes_runtime = daemon_client.hermes_runtime
    paths = daemon_client.config_paths.get_runtime_paths()
    hermes_runtime.save_provider_credentials(
        {
            "id": "deepseek",
            "type": "cloud",
            "env_key": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "hermes_provider": "deepseek",
        },
        "deepseek-chat",
        "placeholder-secret-value",
        paths=paths,
    )
    product_features.update_capability("web_search", enabled=True, paths=paths)
    product_features.create_profile(name="工作助理", instructions="先给结论。", paths=paths)
    product_features.create_task(
        title="导出任务",
        prompt="导出后可恢复",
        due_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="minutes"),
        kind="reminder",
        schedule="once",
        paths=paths,
    )

    exported = product_features.advanced_config_export(paths)
    exported_text = str(exported)
    assert exported["redacted"] is True
    assert "placeholder-secret-value" not in exported_text
    assert exported["not_included"]

    product_features.update_capability("web_search", enabled=False, paths=paths)
    imported = product_features.advanced_config_import(exported, paths=paths)

    assert imported["ok"] is True
    assert imported["applied"]["capabilities"] >= 1
    web_search = [item for item in product_features.list_capabilities(paths) if item["id"] == "web_search"][0]
    assert web_search["enabled"] is True


def test_conversation_turn_product_actions_are_local_wrappers(daemon_client, monkeypatch):
    conversations = daemon_client.conversations
    paths = daemon_client.config_paths.get_runtime_paths()
    client = daemon_client.client
    headers = daemon_client.headers

    conversation = conversations.create_conversation(title="原始对话", paths=paths)
    user = conversations.create_message(
        conversation_id=conversation["id"],
        source="desktop",
        role="user",
        text="帮我整理事项",
        paths=paths,
    )
    attachment_dir = paths.data_dir / "attachments" / "branch-test"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    attachment_path = attachment_dir / "todo.txt"
    attachment_path.write_text("todo", encoding="utf-8")
    source_attachment = conversations.create_attachment_record(
        message_id=user["id"],
        conversation_id=conversation["id"],
        safe_path=attachment_path,
        file_name="todo.txt",
        mime_type="text/plain",
        size_bytes=4,
        summary_status="ready",
        summary_text="待办附件",
        paths=paths,
    )
    conversations.create_message(
        conversation_id=conversation["id"],
        source="assistant",
        role="assistant",
        text="好的。",
        paths=paths,
    )

    summary = client.post(f"/conversations/{conversation['id']}/turns/save-summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["memory"]["source"] == "conversation_summary"

    branch = client.post(
        f"/conversations/{conversation['id']}/turns/branch",
        headers=headers,
        json={"title": "分支对话", "message_id": user["id"]},
    )
    assert branch.status_code == 200
    assert branch.json()["conversation"]["metadata"]["branch_from"] == conversation["id"]
    assert branch.json()["copied_messages"] == 1
    assert branch.json()["copied_attachments"] == 1
    branch_messages = conversations.list_messages(branch.json()["conversation"]["id"], paths=paths)
    assert len(branch_messages) == 1
    assert len(branch_messages[0]["attachments"]) == 1
    copied_attachment = conversations.get_attachment(branch_messages[0]["attachments"][0]["id"], include_safe_path=True, paths=paths)
    assert copied_attachment is not None
    assert copied_attachment["id"] != source_attachment["id"]
    assert copied_attachment["safe_path"] == str(attachment_path)
    assert copied_attachment["metadata"]["copied_from_attachment_id"] == source_attachment["id"]

    undo = client.post(f"/conversations/{conversation['id']}/turns/undo", headers=headers)
    assert undo.status_code == 200
    assert len(undo.json()["removed_message_ids"]) == 2

    conversations.create_message(
        conversation_id=conversation["id"],
        source="desktop",
        role="user",
        text="再试一次",
        paths=paths,
    )

    async def fake_accept(message, *, conversation_id, source, attachments_payload=None):
        return {
            "ok": True,
            "user_message": {"id": "msg_user", "conversation_id": conversation_id, "role": "user", "source": source, "text": message},
            "assistant_message": {
                "id": "msg_assistant",
                "conversation_id": conversation_id,
                "role": "assistant",
                "source": "assistant",
                "text": "accepted",
            },
            "chat": {"ok": True, "accepted": True},
        }

    monkeypatch.setattr(daemon_client.app_module, "_accept_conversation_message", fake_accept)
    retry = client.post(f"/conversations/{conversation['id']}/turns/retry", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["action"] == "retry"
    assert retry.json()["user_message"]["text"] == "再试一次"
