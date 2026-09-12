import pytest
from fastapi import HTTPException
from app.utils.validators import validate_image_bytes
from app.utils.cv_utils import calculate_laplacian_variance, get_image_info


def test_validate_image_bytes_valid(sample_sharp_image_bytes):
    mime = validate_image_bytes(sample_sharp_image_bytes)
    assert mime in ["image/png", "image/jpeg"]


def test_validate_image_bytes_empty():
    with pytest.raises(HTTPException) as exc_info:
        validate_image_bytes(b"")
    assert exc_info.value.status_code == 400


def test_validate_image_bytes_corrupt():
    with pytest.raises(HTTPException) as exc_info:
        validate_image_bytes(b"not_an_image_content_here_just_random_text")
    assert exc_info.value.status_code == 400


def test_laplacian_variance_sharp_vs_blurry(sample_sharp_image_bytes, sample_blurry_image_bytes):
    sharp_score = calculate_laplacian_variance(sample_sharp_image_bytes)
    blurry_score = calculate_laplacian_variance(sample_blurry_image_bytes)
    assert sharp_score > blurry_score
    assert sharp_score > 100.0


def test_get_image_info(sample_sharp_image_bytes):
    info = get_image_info(sample_sharp_image_bytes)
    assert info["width"] == 200
    assert info["height"] == 200
    assert info["blur_score"] > 0
