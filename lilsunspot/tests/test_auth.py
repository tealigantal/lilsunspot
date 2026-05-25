import pytest


def test_providers_requires_valid_runtime_token(daemon_client, auth_headers):
    no_token = daemon_client.client.get("/providers")
    wrong_token = daemon_client.client.get(
        "/providers",
        headers={daemon_client.token_header: "wrong-token"},
    )
    correct_token = daemon_client.client.get("/providers", headers=auth_headers)

    assert no_token.status_code == 403
    assert wrong_token.status_code == 403
    assert correct_token.status_code == 200
    assert isinstance(correct_token.json()["providers"], list)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/runtime/info", None),
        ("get", "/doctor/run", None),
        ("post", "/doctor/run", {}),
        ("get", "/providers/current", None),
        ("get", "/providers/deepseek", None),
        ("post", "/providers/open-key-url", {"provider": "deepseek"}),
        ("post", "/providers/validate-key-format", {"provider": "deepseek", "api_key": "test-key-redacted"}),
        (
            "post",
            "/providers/test",
            {"provider": "deepseek", "model": "deepseek-chat", "api_key": "test-key-redacted"},
        ),
        (
            "post",
            "/providers/save",
            {"provider": "deepseek", "model": "deepseek-chat", "api_key": "test-key-redacted"},
        ),
    ],
)
def test_business_apis_require_runtime_token(daemon_client, method, path, json_body):
    request = getattr(daemon_client.client, method)
    kwargs = {"json": json_body} if json_body is not None else {}

    response = request(path, **kwargs)

    assert response.status_code == 403
