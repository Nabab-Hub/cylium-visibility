import os
from typing import Optional, Any, Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from fastapi import HTTPException, status

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False
    APIError = Exception

from app.config import settings
from app.utils.logger import logger


class GeminiClientWrapper:
    """Wrapper for Google GenAI SDK client with authentication and retry logic."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        if self.api_key and "GEMINI_API_KEY" not in os.environ:
            os.environ["GEMINI_API_KEY"] = self.api_key
        self._client: Optional[Any] = None

    def get_client(self) -> Any:
        """Lazily initializes and returns the GenAI client."""
        if not GOOGLE_GENAI_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="google-genai SDK is not installed.",
            )

        if self._client is None:
            if not self.api_key:
                logger.warning("GEMINI_API_KEY is not configured.")
                self._client = genai.Client()
            else:
                self._client = genai.Client(api_key=self.api_key)

        return self._client

    @retry(
        retry=retry_if_exception_type((APIError, ConnectionError, TimeoutError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        before_sleep=before_sleep_log(logger, 20),
        reraise=True,
    )
    def call_vision_api(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        response_schema: Optional[Any] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """Calls Gemini Vision API with multimodal image part and returns raw text response."""
        # Optimize image size for faster network transfer to vision API
        if len(image_bytes) > 500 * 1024:
            try:
                import io
                from PIL import Image
                with Image.open(io.BytesIO(image_bytes)) as pil_img:
                    if max(pil_img.size) > 1024:
                        pil_img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                        buf = io.BytesIO()
                        pil_img.convert("RGB").save(buf, format="JPEG", quality=85)
                        image_bytes = buf.getvalue()
                        mime_type = "image/jpeg"
            except Exception:
                pass

        client = self.get_client()

        candidates = [model_name or settings.VISIBILITY_MODEL]
        for candidate in [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3-flash-preview",
        ]:
            if candidate not in candidates:
                candidates.append(candidate)

        last_error = None

        for model in candidates:
            try:
                config: Dict[str, Any] = {
                    "temperature": 0.1,
                }
                if response_schema is not None:
                    config["response_mime_type"] = "application/json"
                    config["response_schema"] = response_schema

                contents = [
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ]

                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(**config) if config else None,
                )
                return response.text

            except Exception as e:
                last_error = e
                logger.warning(f"Vision model {model} failed: {e}. Trying next candidate...")
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    break
                continue

        logger.error(f"All Gemini Vision models failed. Last error: {last_error}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini Vision API call failed across models: {str(last_error)}",
        )

    def call_vision_detection(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        model_name: Optional[str] = None,
        schema: Optional[Any] = None,
    ) -> str:
        """Calls vision detection API and returns model response string."""
        return self.call_vision_api(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
            response_schema=schema,
            model_name=model_name,
        )

    def check_connection(self) -> Dict[str, Any]:
        """Validates API key configuration and client initialization."""
        is_configured = bool(self.api_key)
        return {
            "configured": is_configured,
            "visibility_model": settings.VISIBILITY_MODEL,
        }


# Singleton client wrapper
gemini_client_wrapper = GeminiClientWrapper()
