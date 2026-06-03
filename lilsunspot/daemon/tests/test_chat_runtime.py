from __future__ import annotations

import json

import httpx
import pytest


DEEPSEEK_PROVIDER = {
    "id": "deepseek",
    "type": "cloud",
    "env_key": "DEEPSEEK_API_KEY",
    "base_url": "https://api.deepseek.com/v1",
    "hermes_provider": "deepseek",
}


def _mock_chat_http_client(daemon_client, monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def make_client(base_url: str):
        return httpx.AsyncClient(base_url=base_url, transport=transport)

    monkeypatch.setattr(daemon_client.chat_client, "_make_chat_http_client", make_client)


def _save_deepseek(daemon_client, api_key: str = "placeholder-chat-runtime-key") -> None:
    daemon_client.hermes_runtime.save_provider_credentials(
        DEEPSEEK_PROVIDER,
        "deepseek-chat",
        api_key,
        paths=daemon_client.config_paths.get_runtime_paths(),
    )


def test_chat_runtime_cloud_provider_uses_saved_key_without_leaking(daemon_client, monkeypatch):
    secret = "placeholder-chat-runtime-key"
    seen_headers = {}
    seen_payload = {}
    _save_deepseek(daemon_client, secret)

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["authorization"] = request.headers.get("authorization")
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        assert str(request.url) == "https://api.deepseek.com/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "收到。"}}]})

    _mock_chat_http_client(daemon_client, monkeypatch, handler)

    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["engine"] == "hermes_runtime"
    assert body["reply"] == "收到。"
    assert seen_headers["authorization"] == f"Bearer {secret}"
    assert seen_payload["model"] == "deepseek-chat"
    assert seen_payload["messages"][0]["content"] == "你好"
    assert secret not in response.text


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_error"),
    [
        (401, {"error": {"message": "unauthorized"}}, "invalid_key"),
        (402, {"error": {"message": "insufficient credits"}}, "quota_exceeded"),
        (429, {"error": {"message": "rate limit"}}, "rate_limited"),
        (404, {"error": {"message": "model not found"}}, "model_not_found"),
    ],
)
def test_chat_runtime_http_errors_are_mapped_and_redacted(
    daemon_client,
    monkeypatch,
    status_code,
    payload,
    expected_error,
):
    secret = "placeholder-chat-runtime-error-key"
    _save_deepseek(daemon_client, secret)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    _mock_chat_http_client(daemon_client, monkeypatch, handler)

    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == expected_error
    assert secret not in response.text


def test_chat_runtime_network_error_is_human_error(daemon_client, monkeypatch):
    _save_deepseek(daemon_client)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mock chat connection failed", request=request)

    _mock_chat_http_client(daemon_client, monkeypatch, handler)

    response = daemon_client.client.post(
        "/chat/send",
        headers=daemon_client.headers,
        json={"message": "你好"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "network_error"
    assert "连不上模型服务" in body["message"]
