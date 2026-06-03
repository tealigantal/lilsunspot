import asyncio
import json

import httpx

from lilsunspot.daemon import provider_client


OPENROUTER_PROVIDER = {
    "id": "openrouter",
    "type": "cloud",
    "base_url": "https://openrouter.ai/api/v1",
    "default_model": "openai/gpt-4o-mini",
    "env_key": "OPENROUTER_API_KEY",
}


def _mock_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def make_client(base_url: str):
        return httpx.AsyncClient(base_url=base_url, transport=transport)

    monkeypatch.setattr(provider_client, "_make_http_client", make_client)


def test_provider_client_real_chat_probe_success(monkeypatch):
    secret = "placeholder-provider-value"
    seen_headers = {}
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["authorization"] = request.headers.get("authorization")
        seen_payload.update(json.loads(request.content.decode("utf-8")))
        assert request.method == "POST"
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            secret,
        )
    )

    assert result["ok"] is True
    assert result["provider"] == "openrouter"
    assert "验证通过" in result["message"]
    assert seen_headers["authorization"] == f"Bearer {secret}"
    assert seen_payload["model"] == "openai/gpt-4o-mini"
    assert secret not in json.dumps(seen_payload, ensure_ascii=False)
    assert secret not in json.dumps(result, ensure_ascii=False)


def test_provider_client_requires_key_for_cloud_provider():
    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "",
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "invalid_key"


def test_provider_client_invalid_key_is_redacted(monkeypatch):
    secret = "placeholder-provider-secret"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            secret,
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "invalid_key"
    assert secret not in json.dumps(result, ensure_ascii=False)


def test_provider_client_200_without_completion_payload_is_unknown(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "placeholder-provider-value",
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "unknown"


def test_provider_client_missing_model(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "placeholder-provider-value",
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "model_not_found"


def test_provider_client_rate_limit_status_wins(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota exhausted for this minute"}})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "placeholder-provider-value",
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "rate_limited"


def test_provider_client_quota_status(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "insufficient credits"}})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "placeholder-provider-value",
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "quota_exceeded"


def test_provider_client_network_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mock connection failed", request=request)

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "placeholder-provider-value",
        )
    )

    assert result["ok"] is False
    assert result["error_code"] == "network_error"


def test_provider_client_local_provider_can_skip_auth_header(monkeypatch):
    local_provider = {
        "id": "ollama",
        "type": "local",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "llama3.2",
    }
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers["authorization"] = request.headers.get("authorization")
        assert str(request.url) == "http://127.0.0.1:11434/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _mock_client(monkeypatch, handler)

    result = asyncio.run(
        provider_client.test_provider_connection(
            local_provider,
            "llama3.2",
            "",
        )
    )

    assert result["ok"] is True
    assert seen_headers["authorization"] is None
