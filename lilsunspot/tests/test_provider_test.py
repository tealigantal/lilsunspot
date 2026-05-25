import httpx


class FakeAsyncClient:
    status_code = 200
    content = b'{"id":"chatcmpl-test"}'
    post_calls = []
    get_calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def post(self, url, headers=None, json=None):
        self.__class__.post_calls.append((url, headers, json))
        return httpx.Response(self.__class__.status_code, content=self.__class__.content)

    async def get(self, url, headers=None):
        self.__class__.get_calls.append((url, headers))
        return httpx.Response(self.__class__.status_code, content=self.__class__.content)


def test_provider_test_uses_mocked_httpx_success(daemon_client, auth_headers, monkeypatch):
    FakeAsyncClient.status_code = 200
    FakeAsyncClient.content = b'{"id":"chatcmpl-test"}'
    FakeAsyncClient.post_calls = []
    monkeypatch.setattr(daemon_client.providers_module.httpx, "AsyncClient", FakeAsyncClient)
    api_key = "test-key-redacted-provider"

    response = daemon_client.client.post(
        "/providers/test",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": api_key,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["provider"] == "deepseek"
    assert body["model"] == "deepseek-chat"
    assert isinstance(body["latency_ms"], int)
    assert FakeAsyncClient.post_calls
    assert api_key not in str(FakeAsyncClient.post_calls[0][2])
    assert api_key not in response.text


def test_provider_test_classifies_invalid_key(daemon_client, auth_headers, monkeypatch):
    FakeAsyncClient.status_code = 401
    FakeAsyncClient.content = b'{"error":"invalid api key"}'
    FakeAsyncClient.post_calls = []
    monkeypatch.setattr(daemon_client.providers_module.httpx, "AsyncClient", FakeAsyncClient)

    response = daemon_client.client.post(
        "/providers/test",
        headers=auth_headers,
        json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "test-key-redacted-openai",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "invalid_key"


def test_provider_test_ollama_uses_detection_endpoint(daemon_client, auth_headers, monkeypatch):
    FakeAsyncClient.status_code = 200
    FakeAsyncClient.content = b'{"data":[]}'
    FakeAsyncClient.get_calls = []
    monkeypatch.setattr(daemon_client.providers_module.httpx, "AsyncClient", FakeAsyncClient)

    response = daemon_client.client.post(
        "/providers/test",
        headers=auth_headers,
        json={
            "provider": "ollama",
            "model": "llama3.2",
            "api_key": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert FakeAsyncClient.get_calls
    assert FakeAsyncClient.get_calls[0][0].endswith("/models")
