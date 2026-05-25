def test_health_returns_ok(daemon_client):
    response = daemon_client.client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
