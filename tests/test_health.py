def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "gemini_configured" in data
    assert "firebase_connected" in data
    assert "visibility_model" in data
    assert data["status"] in ["healthy", "degraded"]


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Object Visibility & Quality Detection API"
    assert "/detect-visibility" in data["endpoints"]
    assert "/health" in data["endpoints"]
