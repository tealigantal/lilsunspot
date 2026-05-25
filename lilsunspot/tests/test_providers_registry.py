import yaml

from lilsunspot.daemon.providers import PROVIDER_REGISTRY_FILE, load_provider_registry


def test_provider_registry_yaml_is_parseable_and_contains_day2_providers():
    data = yaml.safe_load(PROVIDER_REGISTRY_FILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)

    providers = load_provider_registry()
    provider_ids = {provider["id"] for provider in providers}

    assert {"deepseek", "openrouter", "openai", "kimi", "qwen", "ollama"} <= provider_ids


def test_providers_endpoint_returns_public_provider_list(daemon_client, auth_headers):
    response = daemon_client.client.get("/providers", headers=auth_headers)

    assert response.status_code == 200
    providers = response.json()["providers"]
    assert isinstance(providers, list)
    assert providers
    assert {"id", "display_name", "type", "default_model", "env_key", "notes"} <= set(
        providers[0]
    )
    assert "api_key" not in providers[0]
    assert "key" not in providers[0]


def test_provider_detail_returns_404_for_unknown_provider(daemon_client, auth_headers):
    response = daemon_client.client.get("/providers/not-a-provider", headers=auth_headers)

    assert response.status_code == 404
    assert "not-a-provider" in response.json()["detail"]
