from __future__ import annotations


def test_product_feature_endpoints_require_token(daemon_client):
    response = daemon_client.client.get("/diagnostics/summary")

    assert response.status_code == 403


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
    assert any("还没有设置 AI 服务" in item for item in model.json()["limitations"])

    capabilities = client.get("/product/capabilities", headers=headers)
    assert capabilities.status_code == 200
    capability_ids = {item["id"] for item in capabilities.json()["capabilities"]}
    assert {"web_search", "file_read", "reminders", "weixin_send"} <= capability_ids

    toggled = client.patch("/product/capabilities/web_search", headers=headers, json={"enabled": True})
    assert toggled.status_code == 200
    assert toggled.json()["capability"]["enabled"] is True


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
