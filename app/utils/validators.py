import io
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, status
from app.config import settings


def validate_image_bytes(image_bytes: bytes, max_size_mb: int = None) -> str:
    """
    Validates image byte content:
    - Checks file size against MAX_IMAGE_SIZE_MB
    - Attempts PIL decoding to ensure valid image structure
    - Returns identified MIME type
    """
    max_mb = max_size_mb if max_size_mb is not None else settings.MAX_IMAGE_SIZE_MB
    size_bytes = len(image_bytes)

    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided image payload is empty.",
        )

    if size_bytes > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail=f"Image size ({size_bytes / (1024 * 1024):.2f} MB) exceeds maximum allowed size of {max_mb} MB.",
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()
            fmt = img.format
    except (UnidentifiedImageError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupted image data: {str(e)}",
        )

    # Map PIL format to MIME type
    format_mime_map = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "HEIC": "image/heic",
        "HEIF": "image/heif",
        "BMP": "image/bmp",
        "TIFF": "image/tiff",
    }
    mime_type = format_mime_map.get(fmt.upper() if fmt else "", "application/octet-stream")

    if mime_type not in settings.ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image format: {fmt} ({mime_type}). Allowed formats: {settings.ALLOWED_IMAGE_MIME_TYPES}",
        )

    return mime_type
