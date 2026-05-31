import asyncio
import json

from lilsunspot.daemon import provider_client


OPENROUTER_PROVIDER = {
    "id": "openrouter",
    "type": "cloud",
    "base_url": "https://openrouter.ai/api/v1",
    "default_model": "openai/gpt-4o-mini",
    "env_key": "OPENROUTER_API_KEY",
}


def test_provider_client_placeholder_success():
    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            "placeholder-provider-value",
        )
    )

    assert result["ok"] is True
    assert result["provider"] == "openrouter"
    assert "未发起真实服务调用" in result["message"]


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


def test_provider_client_does_not_echo_key():
    secret = "placeholder-provider-secret"

    result = asyncio.run(
        provider_client.test_provider_connection(
            OPENROUTER_PROVIDER,
            "openai/gpt-4o-mini",
            secret,
        )
    )

    assert secret not in json.dumps(result, ensure_ascii=False)
