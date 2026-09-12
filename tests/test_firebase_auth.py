import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import verify_api_key
from app.utils.helpers import hash_api_key, current_timestamp_ms


@pytest.fixture
def clean_client():
    """Client without default dependency overrides to test actual verify_api_key logic."""
    app.dependency_overrides.pop(verify_api_key, None)
    yield TestClient(app)


def test_missing_api_key_returns_401(clean_client):
    response = clean_client.post("/detect-visibility", json={"image_base64": "dummy"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "missing_api_key"


def test_invalid_api_key_returns_401(clean_client):
    response = clean_client.post(
        "/detect-visibility",
        json={"image_base64": "dummy"},
        headers={"X-API-Key": "non_existent_key_12345"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_api_key"


def test_inactive_api_key_raises_403():
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {
        "status": "revoked",
        "monthlyLimit": 1000,
        "requestCount": 10,
    }
    mock_doc.reference = "ref_1"
    mock_doc.id = "doc_1"

    query_mock = MagicMock()
    query_mock.where.return_value.limit.return_value.stream.return_value = [mock_doc]
    mock_db.collection.return_value = query_mock

    with patch("app.api.deps.get_firestore_client", return_value=mock_db):
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(api_key="nsk_live_testkey")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "api_key_inactive"


def test_monthly_limit_reached_raises_429():
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {
        "status": "active",
        "monthlyLimit": 100,
        "requestCount": 100,
    }
    mock_doc.reference = "ref_2"
    mock_doc.id = "doc_2"

    query_mock = MagicMock()
    query_mock.where.return_value.limit.return_value.stream.return_value = [mock_doc]
    mock_db.collection.return_value = query_mock

    with patch("app.api.deps.get_firestore_client", return_value=mock_db):
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(api_key="nsk_live_testlimit")
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["error"] == "monthly_limit_reached"


def test_valid_active_key_returns_metadata():
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {
        "status": "active",
        "monthlyLimit": 1000,
        "requestCount": 42,
        "userId": "user_xyz",
        "plan": "pro",
    }
    mock_doc.reference = "ref_3"
    mock_doc.id = "doc_3"

    query_mock = MagicMock()
    query_mock.where.return_value.limit.return_value.stream.return_value = [mock_doc]
    mock_db.collection.return_value = query_mock

    with patch("app.api.deps.get_firestore_client", return_value=mock_db):
        key_data = verify_api_key(api_key="nsk_live_validkey")
        assert key_data["key_id"] == "doc_3"
        assert key_data["user_id"] == "user_xyz"
        assert key_data["plan"] == "pro"
        assert key_data["status"] == "active"
        assert key_data["monthly_limit"] == 1000
        assert key_data["request_count"] == 42
