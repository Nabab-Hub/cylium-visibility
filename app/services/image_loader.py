import io
import os
import base64
import hashlib
from dataclasses import dataclass
from typing import Optional
from PIL import Image
import httpx
from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.utils.validators import validate_image_bytes
from app.utils.cv_utils import calculate_laplacian_variance
from app.utils.logger import logger


@dataclass
class LoadedImage:
    """Standardized internal representation of an ingested image."""
    image_bytes: bytes
    pil_image: Image.Image
    mime_type: str
    sha256: str
    width: int
    height: int
    blur_score: float


class ImageLoaderService:
    """Handles decoding, downloading, and loading images from multiple source types."""

    @staticmethod
    async def load_from_base64(b64_string: str) -> bytes:
        """Decodes raw base64 or Data URI string to bytes."""
        try:
            if not b64_string or not b64_string.strip():
                raise ValueError("Base64 string cannot be empty.")

            clean_str = b64_string.strip()
            # Strip data URI prefix if present (e.g. data:image/png;base64,...)
            if "," in clean_str and "base64" in clean_str.split(",")[0]:
                clean_str = clean_str.split(",", 1)[1]

            # Fix padding if needed
            missing_padding = len(clean_str) % 4
            if missing_padding:
                clean_str += "=" * (4 - missing_padding)

            # Validate base64 characters strictly
            return base64.b64decode(clean_str, validate=True)
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image payload: {str(e)}",
            )

    @staticmethod
    async def load_from_url(url: str) -> bytes:
        """Downloads image bytes from an HTTP/HTTPS URL."""
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image URL must start with http:// or https://",
            )

        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to fetch image from URL: received HTTP status {response.status_code}",
                    )
                return response.content
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Connection timed out while fetching image from {url}",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching image from URL '{url}': {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch image from URL: {str(e)}",
            )

    @staticmethod
    async def load_from_path(file_path: str) -> bytes:
        """Reads image bytes from a local filesystem path."""
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image file not found at path: {file_path}",
            )

        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specified path is not a file: {file_path}",
            )

        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading image file from '{file_path}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not read image file from disk: {str(e)}",
            )

    @classmethod
    async def load_image(
        cls,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
        image_path: Optional[str] = None,
        upload_file: Optional[UploadFile] = None,
    ) -> LoadedImage:
        """
        Orchestrates image ingestion from one of the supported sources:
        1. Multipart file upload
        2. Base64 encoded string
        3. Web URL
        4. Local file path
        """
        image_bytes: bytes

        if upload_file is not None:
            try:
                image_bytes = await upload_file.read()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read uploaded file: {str(e)}",
                )
        elif image_base64 is not None:
            image_bytes = await cls.load_from_base64(image_base64)
        elif image_url is not None:
            image_bytes = await cls.load_from_url(image_url)
        elif image_path is not None:
            image_bytes = await cls.load_from_path(image_path)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No image source provided.",
            )

        # Validate byte payload and format
        mime_type = validate_image_bytes(image_bytes)

        # Parse with PIL for dimensions
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image.load()
            width, height = pil_image.size
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process image with PIL: {str(e)}",
            )

        # Compute SHA-256 fingerprint for caching
        sha256 = hashlib.sha256(image_bytes).hexdigest()

        # Compute blur telemetry using Laplacian variance
        blur_score = calculate_laplacian_variance(image_bytes)

        return LoadedImage(
            image_bytes=image_bytes,
            pil_image=pil_image,
            mime_type=mime_type,
            sha256=sha256,
            width=width,
            height=height,
            blur_score=blur_score,
        )
