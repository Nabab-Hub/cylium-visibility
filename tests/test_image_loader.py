import pytest
from fastapi import HTTPException
from app.services.image_loader import ImageLoaderService


@pytest.mark.asyncio
async def test_load_from_base64_plain(sample_base64_sharp):
    raw_bytes = await ImageLoaderService.load_from_base64(sample_base64_sharp)
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0


@pytest.mark.asyncio
async def test_load_from_base64_data_uri(sample_data_uri_sharp):
    raw_bytes = await ImageLoaderService.load_from_base64(sample_data_uri_sharp)
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0


@pytest.mark.asyncio
async def test_load_from_base64_invalid():
    with pytest.raises(HTTPException) as exc_info:
        await ImageLoaderService.load_from_base64("not_a_valid_base64_@@@!!!")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_load_from_path_missing():
    with pytest.raises(HTTPException) as exc_info:
        await ImageLoaderService.load_from_path("non_existent_image_12345.jpg")
    assert exc_info.value.status_code == 404
