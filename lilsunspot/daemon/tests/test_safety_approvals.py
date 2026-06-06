from __future__ import annotations


def _create_weixin_approval(daemon_client):
    return daemon_client.client.post(
        "/gateway/weixin/send",
        headers=daemon_client.headers,
        json={"recipient": "文件传输助手", "message": "帮我提醒一下明天开会。"},
    )


def test_weixin_send_requires_token_and_creates_pending_approval(daemon_client):
    client = daemon_client.client

    assert client.post(
        "/gateway/weixin/send",
        json={"recipient": "文件传输助手", "message": "你好"},
    ).status_code == 403

    response = _create_weixin_approval(daemon_client)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "approval_required"
    assert body["approval_required"] is True
    assert "不会直接发送" in body["message"]

    approval = body["approval"]
    assert approval["operation"] == "send_weixin_message"
    assert approval["status"] == "pending"
    assert approval["source"] == "weixin"
    assert approval["details"]["recipient"] == "文件传输助手"
    assert approval["details"]["message_preview"] == "帮我提醒一下明天开会。"
    assert approval["details"]["message_length"] == len("帮我提醒一下明天开会。")

    paths = daemon_client.config_paths.get_runtime_paths()
    assert (paths.data_dir / "safety-approvals.json").exists()
    assert not (paths.hermes_home / "safety-approvals.json").exists()
    assert daemon_client.token not in response.text


def test_approval_decision_updates_pending_and_history(daemon_client):
    client = daemon_client.client
    headers = daemon_client.headers
    approval_id = _create_weixin_approval(daemon_client).json()["approval"]["id"]

    pending = client.get("/safety/approvals", headers=headers)
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()["pending"]] == [approval_id]

    decided = client.post(
        f"/safety/approvals/{approval_id}/decide",
        headers=headers,
        json={"decision": "approved"},
    )
    assert decided.status_code == 200
    assert decided.json()["ok"] is True
    assert decided.json()["approval"]["status"] == "approved"

    after = client.get("/safety/approvals", headers=headers)
    assert after.status_code == 200
    assert after.json()["pending"] == []
    assert [item["id"] for item in after.json()["history"]] == [approval_id]

    repeated = client.post(
        f"/safety/approvals/{approval_id}/decide",
        headers=headers,
        json={"decision": "rejected"},
    )
    assert repeated.status_code == 400
    assert "已经处理过" in repeated.text


def test_weixin_command_handle_mode_and_approval_decision(daemon_client):
    client = daemon_client.client
    headers = daemon_client.headers
    approval_id = _create_weixin_approval(daemon_client).json()["approval"]["id"]

    help_response = client.post("/gateway/weixin/commands/handle", headers=headers, json={"text": "/help"})
    assert help_response.status_code == 200
    assert help_response.json()["ok"] is True
    assert any(item["name"] == "/reject" for item in help_response.json()["commands"])

    mode_response = client.post(
        "/gateway/weixin/commands/handle",
        headers=headers,
        json={"text": "/mode pragmatic"},
    )
    assert mode_response.status_code == 200
    assert mode_response.json()["ok"] is True
    assert mode_response.json()["mode"]["current"] == "pragmatic"

    approve_response = client.post(
        "/gateway/weixin/commands/handle",
        headers=headers,
        json={"text": f"/approve {approval_id}"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["ok"] is True
    assert approve_response.json()["approval"]["status"] == "approved"

    unknown = client.post("/gateway/weixin/commands/handle", headers=headers, json={"text": "/unknown"})
    assert unknown.status_code == 200
    assert unknown.json()["ok"] is False
    assert "没有识别" in unknown.json()["message"]


def test_safety_approval_request_redacts_sensitive_detail_fields(daemon_client):
    response = daemon_client.client.post(
        "/safety/approvals/request",
        headers=daemon_client.headers,
        json={
            "operation": "credential_access",
            "summary": f"读取凭据 {daemon_client.token}",
            "details": {
                "token": daemon_client.token,
                "api_key": "placeholder-api-key",
                "nested": {"secret": "placeholder-secret"},
                "comment": daemon_client.token,
                "note": "普通说明",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is True
    assert body["approval"]["summary"] == "读取凭据 [已隐藏]"
    assert body["approval"]["details"]["token"] == "[已隐藏]"
    assert body["approval"]["details"]["api_key"] == "[已隐藏]"
    assert body["approval"]["details"]["nested"]["secret"] == "[已隐藏]"
    assert body["approval"]["details"]["comment"] == "[已隐藏]"
    assert body["approval"]["details"]["note"] == "普通说明"
    assert daemon_client.token not in response.text
    assert "placeholder-api-key" not in response.text
    assert "placeholder-secret" not in response.text
