import json
from unittest.mock import patch


def test_detect_visibility_json_success(client, sample_base64_sharp):
    mock_gemini_output = json.dumps({
        "object_name": "Checkerboard Pattern",
        "visibility": True,
        "confidence": 0.98,
        "message": "The pattern is sharp, clear, and perfectly centered.",
        "is_blurry": False,
        "is_occluded": False,
        "is_cut_off": False
    })

    with patch("app.services.gemini_client.gemini_client_wrapper.call_vision_detection", return_value=mock_gemini_output):
        response = client.post(
            "/detect-visibility",
            json={"image_base64": sample_base64_sharp}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["object_name"] == "Checkerboard Pattern"
        assert data["visibility"] is True
        assert data["confidence"] == 0.98
        assert data["cached"] is False
        assert data["blur_score"] > 0

        # Test caching on second identical request
        second_response = client.post(
            "/detect-visibility",
            json={"image_base64": sample_base64_sharp}
        )
        assert second_response.status_code == 200
        second_data = second_response.json()
        assert second_data["cached"] is True


def test_detect_visibility_markdown_fences(client, sample_base64_sharp):
    mock_gemini_output = """```json
    {
        "object_name": "Water Bottle",
        "visibility": false,
        "confidence": 0.35,
        "message": "Object is blurry and partially out of frame.",
        "is_blurry": true,
        "is_occluded": false,
        "is_cut_off": true
    }
    ```"""

    with patch("app.services.gemini_client.gemini_client_wrapper.call_vision_detection", return_value=mock_gemini_output):
        response = client.post(
            "/detect-visibility",
            json={"image_base64": sample_base64_sharp}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object_name"] == "Water Bottle"
        assert data["visibility"] is False
        assert data["is_cut_off"] is True
        assert data["is_blurry"] is True


def test_detect_visibility_upload_success(client, sample_sharp_image_bytes):
    mock_gemini_output = json.dumps({
        "object_name": "Uploaded Product",
        "visibility": True,
        "confidence": 0.92,
        "message": "Good visibility and clear framing.",
        "is_blurry": False,
        "is_occluded": False,
        "is_cut_off": False
    })

    with patch("app.services.gemini_client.gemini_client_wrapper.call_vision_detection", return_value=mock_gemini_output):
        response = client.post(
            "/detect-visibility/upload",
            files={"file": ("test_upload.png", sample_sharp_image_bytes, "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object_name"] == "Uploaded Product"
        assert data["visibility"] is True


def test_detect_visibility_invalid_multiple_sources(client, sample_base64_sharp):
    response = client.post(
        "/detect-visibility",
        json={
            "image_base64": sample_base64_sharp,
            "image_url": "https://example.com/image.jpg"
        }
    )
    assert response.status_code == 422


def test_detect_visibility_no_source(client):
    response = client.post(
        "/detect-visibility",
        json={}
    )
    assert response.status_code == 422
