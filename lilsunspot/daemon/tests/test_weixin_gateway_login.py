from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace


def _patch_weixin_gateway(monkeypatch, responses):
    import lilsunspot.daemon.gateway as gateway

    pending = list(responses)

    async def fake_api_get(*, base_url: str, endpoint: str) -> dict[str, object]:
        assert base_url.startswith("https://")
        if endpoint == gateway._weixin_login_qr_endpoint():
            return {
                "qrcode": "unit-test-qr",
                "qrcode_img_content": "https://weixin.example/scan/unit-test-qr",
            }
        assert endpoint.startswith("ilink/bot/get_qrcode_status")
        if not pending:
            return {"status": "wait"}
        return pending.pop(0)

    monkeypatch.setattr(gateway, "_weixin_requirements_available", lambda: True)
    monkeypatch.setattr(gateway, "_weixin_api_get", fake_api_get)
    monkeypatch.setattr(gateway, "_make_qr_image_data_url", lambda qr_payload: "data:image/svg+xml;base64,unit-test-qr")
    return gateway


class FakeWeixinAdapter:
    def __init__(self):
        self.handler = None
        self.fatal_handler = None
        self.is_connected = False
        self.disconnected = False

    def set_message_handler(self, handler):
        self.handler = handler

    def set_fatal_error_handler(self, handler):
        self.fatal_handler = handler

    async def connect(self):
        self.is_connected = True
        return True

    async def disconnect(self):
        self.disconnected = True
        self.is_connected = False


def test_weixin_login_routes_require_token(daemon_client):
    client = daemon_client.client

    assert client.get("/gateway/weixin/status").status_code == 403
    assert client.get("/gateway/weixin/commands").status_code == 403
    assert client.post("/gateway/weixin/commands/handle", json={"text": "/help"}).status_code == 403
    assert client.post("/gateway/weixin/login/start").status_code == 403
    assert client.get("/gateway/weixin/login/status").status_code == 403
    assert client.post("/gateway/weixin/disconnect").status_code == 403


def test_weixin_qr_login_confirm_saves_credentials_without_response_leak(daemon_client, monkeypatch):
    credential_value = "unit-test-credential-value"
    fake_adapter = FakeWeixinAdapter()

    def make_adapter(credentials):
        assert credentials["account_id"] == "bot_account_unit_test"
        assert credentials["token"] == credential_value
        assert credentials["user_id"] == "user_unit_test"
        return fake_adapter

    monkeypatch.setattr(daemon_client.weixin_runtime, "_make_weixin_adapter", make_adapter)
    gateway = _patch_weixin_gateway(
        monkeypatch,
        [
            {"status": "scaned"},
            {
                "status": "confirmed",
                "ilink_bot_id": "bot_account_unit_test",
                "bot_token": credential_value,
                "baseurl": "https://ilink-unit.example",
                "ilink_user_id": "user_unit_test",
            },
        ],
    )

    client = daemon_client.client
    headers = daemon_client.headers

    start = client.post("/gateway/weixin/login/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["status"] == "qr_pending"
    assert start.json()["bot_profile"] == {
        "nickname": "小黑子",
        "avatar_asset": "lilsunspot-icon.png",
        "avatar_alt": "小黑子头像",
    }
    assert start.json()["login"]["qr_payload_kind"] == "url"
    assert start.json()["login"]["qr_image_data_url"].startswith("data:image/svg+xml;base64,")
    assert "clawbot" not in start.text.lower()
    assert credential_value not in start.text

    scanned = client.get("/gateway/weixin/login/status", headers=headers)
    assert scanned.status_code == 200
    assert scanned.json()["status"] == "scanned"
    assert "手机微信" in scanned.json()["message"]

    confirmed = client.get("/gateway/weixin/login/status", headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["connected"] is True
    assert confirmed.json()["status"] == "connected"
    assert confirmed.json()["runtime"]["state"] == "running"
    assert fake_adapter.is_connected is True
    assert fake_adapter.handler is not None
    assert "account" not in confirmed.text.lower()
    assert credential_value not in confirmed.text

    paths = daemon_client.config_paths.get_runtime_paths()
    state = json.loads((paths.data_dir / "weixin-state.json").read_text(encoding="utf-8"))
    assert state["account_id"] == "bot_account_unit_test"
    assert "token" not in state
    account_file = paths.hermes_home / "weixin" / "accounts" / "bot_account_unit_test.json"
    assert account_file.exists()
    assert credential_value in account_file.read_text(encoding="utf-8")
    assert not (paths.data_dir / ".hermes" / "weixin-state.json").exists()

    status = gateway.weixin_status()
    assert status["status"] == "connected"
    assert status["capabilities"]["private_chat"] is True
    assert status["bot_profile"]["nickname"] == "小黑子"


def test_weixin_qr_expiry_and_disconnect_clear_product_state(daemon_client, monkeypatch):
    gateway = _patch_weixin_gateway(monkeypatch, [])
    client = daemon_client.client
    headers = daemon_client.headers

    start = client.post("/gateway/weixin/login/start", headers=headers)
    assert start.status_code == 200
    assert gateway._active_login is not None
    gateway._active_login.expires_at = time.time() - 1

    expired = client.get("/gateway/weixin/login/status", headers=headers)
    assert expired.status_code == 200
    assert expired.json()["status"] == "qr_expired"
    assert "过期" in expired.json()["message"]

    paths = daemon_client.config_paths.get_runtime_paths()
    state_path = paths.data_dir / "weixin-state.json"
    state_path.write_text(
        json.dumps({"account_id": "bot_account_to_clear"}, ensure_ascii=False),
        encoding="utf-8",
    )
    account_dir = paths.hermes_home / "weixin" / "accounts"
    account_dir.mkdir(parents=True, exist_ok=True)
    account_file = account_dir / "bot_account_to_clear.json"
    account_file.write_text(json.dumps({"token": "stored-value"}, ensure_ascii=False), encoding="utf-8")

    disconnected = client.post("/gateway/weixin/disconnect", headers=headers)
    assert disconnected.status_code == 200
    assert disconnected.json()["status"] == "not_configured"
    assert not state_path.exists()
    assert not account_file.exists()

    orphan_file = account_dir / "orphan_account.json"
    orphan_file.write_text(json.dumps({"token": "stored-value"}, ensure_ascii=False), encoding="utf-8")
    assert client.get("/gateway/weixin/status", headers=headers).json()["status"] == "connected"
    disconnected_again = client.post("/gateway/weixin/disconnect", headers=headers)
    assert disconnected_again.status_code == 200
    assert not orphan_file.exists()


def test_weixin_login_start_reports_missing_runtime_components(daemon_client, monkeypatch):
    import lilsunspot.daemon.gateway as gateway

    monkeypatch.setattr(gateway, "_weixin_requirements_available", lambda: False)
    response = daemon_client.client.post("/gateway/weixin/login/start", headers=daemon_client.headers)

    assert response.status_code == 503
    assert "微信网关缺少运行组件" in response.text


def test_weixin_login_start_rejects_missing_scannable_qr_payload(daemon_client, monkeypatch):
    import lilsunspot.daemon.gateway as gateway

    async def fake_api_get(*, base_url: str, endpoint: str) -> dict[str, object]:
        assert endpoint == gateway._weixin_login_qr_endpoint()
        return {"qrcode": "unit-test-status-token"}

    monkeypatch.setattr(gateway, "_weixin_requirements_available", lambda: True)
    monkeypatch.setattr(gateway, "_weixin_api_get", fake_api_get)

    response = daemon_client.client.post("/gateway/weixin/login/start", headers=daemon_client.headers)

    assert response.status_code == 503
    assert "微信二维码内容缺失" in response.text
    assert gateway._active_login is None


def test_weixin_login_start_does_not_restore_session_after_disconnect(daemon_client, monkeypatch):
    import lilsunspot.daemon.gateway as gateway

    async def run_race():
        release = asyncio.Event()

        async def fake_api_get(*, base_url: str, endpoint: str) -> dict[str, object]:
            assert endpoint == gateway._weixin_login_qr_endpoint()
            await release.wait()
            return {
                "qrcode": "late-unit-qr",
                "qrcode_img_content": "https://weixin.example/scan/late-unit-qr",
            }

        monkeypatch.setattr(gateway, "_weixin_requirements_available", lambda: True)
        monkeypatch.setattr(gateway, "_weixin_api_get", fake_api_get)
        monkeypatch.setattr(gateway, "_make_qr_image_data_url", lambda qr_payload: "data:image/svg+xml;base64,late")

        task = asyncio.create_task(gateway.start_weixin_login())
        await asyncio.sleep(0)
        disconnected = gateway.disconnect_weixin()
        release.set()
        late_result = await task
        return disconnected, late_result

    disconnected, late_result = asyncio.run(run_race())

    assert disconnected["status"] == "not_configured"
    assert late_result["ok"] is False
    assert "取代" in late_result["message"]
    assert gateway._active_login is None


def test_weixin_login_start_ignores_slow_result_after_new_refresh(daemon_client, monkeypatch):
    import lilsunspot.daemon.gateway as gateway

    async def run_race():
        first_started = asyncio.Event()
        first_release = asyncio.Event()
        calls = 0

        async def fake_api_get(*, base_url: str, endpoint: str) -> dict[str, object]:
            nonlocal calls
            assert endpoint == gateway._weixin_login_qr_endpoint()
            calls += 1
            if calls == 1:
                first_started.set()
                await first_release.wait()
                return {
                    "qrcode": "slow-unit-qr",
                    "qrcode_img_content": "https://weixin.example/scan/slow-unit-qr",
                }
            return {
                "qrcode": "fresh-unit-qr",
                "qrcode_img_content": "https://weixin.example/scan/fresh-unit-qr",
            }

        monkeypatch.setattr(gateway, "_weixin_requirements_available", lambda: True)
        monkeypatch.setattr(gateway, "_weixin_api_get", fake_api_get)
        monkeypatch.setattr(gateway, "_make_qr_image_data_url", lambda qr_payload: "data:image/svg+xml;base64,fresh")

        slow_task = asyncio.create_task(gateway.start_weixin_login())
        await first_started.wait()
        fresh_result = await gateway.start_weixin_login()
        first_release.set()
        slow_result = await slow_task
        return fresh_result, slow_result

    fresh_result, slow_result = asyncio.run(run_race())

    assert fresh_result["ok"] is True
    assert fresh_result["status"] == "qr_pending"
    assert fresh_result["login"]["qr_payload"] == "https://weixin.example/scan/fresh-unit-qr"
    assert slow_result["ok"] is False
    assert "取代" in slow_result["message"]
    assert gateway._active_login is not None
    assert gateway._active_login.qrcode == "fresh-unit-qr"


def test_weixin_login_status_does_not_save_credentials_after_disconnect(daemon_client, monkeypatch):
    import lilsunspot.daemon.gateway as gateway

    credential_value = "slow-status-credential-value"

    async def run_race():
        status_started = asyncio.Event()
        status_release = asyncio.Event()

        async def fake_api_get(*, base_url: str, endpoint: str) -> dict[str, object]:
            if endpoint == gateway._weixin_login_qr_endpoint():
                return {
                    "qrcode": "status-race-qr",
                    "qrcode_img_content": "https://weixin.example/scan/status-race-qr",
                }
            assert endpoint.startswith("ilink/bot/get_qrcode_status")
            status_started.set()
            await status_release.wait()
            return {
                "status": "confirmed",
                "ilink_bot_id": "bot_status_race",
                "bot_token": credential_value,
                "baseurl": "https://ilink-status-race.example",
                "ilink_user_id": "user_status_race",
            }

        monkeypatch.setattr(gateway, "_weixin_requirements_available", lambda: True)
        monkeypatch.setattr(gateway, "_weixin_api_get", fake_api_get)
        monkeypatch.setattr(gateway, "_make_qr_image_data_url", lambda qr_payload: "data:image/svg+xml;base64,status-race")

        started = await gateway.start_weixin_login()
        poll_task = asyncio.create_task(gateway.poll_weixin_login_status())
        await status_started.wait()
        disconnected = gateway.disconnect_weixin()
        status_release.set()
        late_poll = await poll_task
        return started, disconnected, late_poll

    started, disconnected, late_poll = asyncio.run(run_race())

    assert started["status"] == "qr_pending"
    assert disconnected["status"] == "not_configured"
    assert late_poll["ok"] is False
    assert "取代" in late_poll["message"]
    assert gateway._active_login is None

    paths = daemon_client.config_paths.get_runtime_paths()
    state_path = paths.data_dir / "weixin-state.json"
    account_file = paths.hermes_home / "weixin" / "accounts" / "bot_status_race.json"
    assert not state_path.exists()
    assert not account_file.exists()


def test_weixin_runtime_fake_event_handles_command_and_chat(daemon_client, monkeypatch):
    runtime = daemon_client.weixin_runtime

    help_reply = asyncio.run(runtime.handle_inbound_weixin_event(SimpleNamespace(text="/help")))
    assert "可用命令" in help_reply
    assert runtime.weixin_runtime_status()["last_inbound_at"]
    assert runtime.weixin_runtime_status()["last_reply_at"]

    async def fake_handle(event):
        assert event.text == "你好"
        return {"ok": True, "message": "微信私聊回复已生成。", "chat": {"reply": "这是微信回复。"}}

    monkeypatch.setattr(runtime, "handle_weixin_message_event", fake_handle)
    chat_reply = asyncio.run(runtime.handle_inbound_weixin_event(SimpleNamespace(text="你好")))
    assert chat_reply == "这是微信回复。"


def test_daemon_lifespan_auto_starts_weixin_only_after_model_config(daemon_client, monkeypatch):
    app_module = daemon_client.app_module
    start_calls = []
    stop_calls = []

    async def fake_start(paths):
        start_calls.append(paths)
        return {"state": "running"}

    async def fake_stop():
        stop_calls.append(True)
        return {"state": "stopped"}

    monkeypatch.setattr(app_module, "start_weixin_runtime", fake_start)
    monkeypatch.setattr(app_module, "stop_weixin_runtime", fake_stop)

    async def run_lifespan_once():
        async with app_module.lifespan(app_module.app):
            pass

    asyncio.run(run_lifespan_once())
    assert start_calls == []
    assert stop_calls == [True]

    save = daemon_client.client.post(
        "/providers/save",
        headers=daemon_client.headers,
        json={"provider": "ollama", "model": "llama3.2", "api_key": ""},
    )
    assert save.status_code == 200

    asyncio.run(run_lifespan_once())
    assert start_calls == [app_module.paths]
    assert stop_calls == [True, True]
