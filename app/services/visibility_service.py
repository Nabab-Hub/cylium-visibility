import re
import json
from typing import Optional
from fastapi import HTTPException, status

from app.schemas.visibility_schema import (
    GeminiVisibilityRawOutput,
    VisibilityResponse,
)
from app.services.image_loader import LoadedImage
from app.services.gemini_client import gemini_client_wrapper
from app.services.cache_service import cache_service
from app.config import settings
from app.utils.logger import logger
from app.utils.cv_utils import analyze_object_visibility_cv


DEFAULT_VISIBILITY_PROMPT = """You are an expert computer vision and image quality inspection assistant.
Analyze this image carefully:
1. Identify the primary or most prominent object (product, bottle, fruit, person, document, etc.). If none is recognizable, return 'Unknown'.
2. Determine if this primary object is CLEARLY and FULLY visible.
   - Set visibility to True only if the object is sharp, well-lit, unobstructed, and largely in frame.
   - Set visibility to False if the object is blurry, heavily occluded, cut off, or unrecognizable.
3. Provide an accurate confidence score between 0.0 and 1.0.
4. Provide a clear, professional diagnostic message.
5. Accurately flag individual boolean flags: is_blurry, is_occluded, is_cut_off.

Output must strictly adhere to the requested JSON schema."""


class VisibilityService:
    """Orchestrates image visibility detection using Gemini Vision and OpenCV metrics."""

    @staticmethod
    def _extract_json_from_text(raw_text: str) -> dict:
        """Robustly extracts JSON object from raw model string response."""
        text = raw_text.strip()

        # Check for markdown code blocks (```json ... ```)
        json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_block_match:
            text = json_block_match.group(1).strip()
        elif "{" in text and "}" in text:
            # Extract first outer brace block
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}. Raw: {raw_text[:200]}")
            # Fallback heuristic cleanup
            cleaned = re.sub(r",\s*\}", "}", text)  # remove trailing commas
            cleaned = re.sub(r",\s*\]", "]", cleaned)
            return json.loads(cleaned)

    @classmethod
    async def detect_visibility(
        cls,
        loaded_image: LoadedImage,
        custom_prompt: Optional[str] = None,
        use_cache: bool = True,
    ) -> VisibilityResponse:
        """Runs visibility and quality detection on a loaded image."""
        cache_key = f"visibility:{loaded_image.sha256}"

        # 1. Check Cache
        if use_cache:
            cached_data = cache_service.get(cache_key)
            if cached_data is not None:
                logger.info(f"Cache hit for visibility check (hash={loaded_image.sha256[:8]})")
                cached_resp = VisibilityResponse(**cached_data)
                cached_resp.cached = True
                return cached_resp

        # 2. Call Gemini Multimodal Vision Model
        prompt = custom_prompt or DEFAULT_VISIBILITY_PROMPT
        logger.info(f"Calling Gemini vision model for visibility detection (hash={loaded_image.sha256[:8]})")

        try:
            import asyncio
            raw_output_text = await asyncio.to_thread(
                gemini_client_wrapper.call_vision_detection,
                image_bytes=loaded_image.image_bytes,
                mime_type=loaded_image.mime_type,
                prompt=prompt,
                model_name=settings.VISIBILITY_MODEL,
                schema=GeminiVisibilityRawOutput,
            )

            # 3. Parse Gemini JSON Output
            parsed_dict = cls._extract_json_from_text(raw_output_text)
            gemini_result = GeminiVisibilityRawOutput(**parsed_dict)

            # 4. Integrate OpenCV Blur Telemetry
            is_blurry = gemini_result.is_blurry
            if is_blurry is None:
                is_blurry = loaded_image.blur_score < settings.LAPLACIAN_BLUR_THRESHOLD

            response = VisibilityResponse(
                object_name=gemini_result.object_name,
                visibility=gemini_result.visibility,
                confidence=round(gemini_result.confidence, 2),
                message=gemini_result.message,
                is_blurry=is_blurry,
                is_occluded=gemini_result.is_occluded,
                is_cut_off=gemini_result.is_cut_off,
                blur_score=loaded_image.blur_score,
                cached=False,
            )

        except Exception as e:
            logger.warning(f"Gemini Vision API call failed ({e}). Falling back to OpenCV heuristic visibility analysis.")
            cv_res = analyze_object_visibility_cv(loaded_image.image_bytes)
            response = VisibilityResponse(
                object_name=cv_res["object_name"],
                visibility=cv_res["visibility"],
                confidence=cv_res["confidence"],
                message=cv_res["message"],
                is_blurry=cv_res["is_blurry"],
                is_occluded=False,
                is_cut_off=cv_res["is_cut_off"],
                blur_score=loaded_image.blur_score,
                cached=False,
            )

        # 5. Store in Cache
        if use_cache:
            cache_service.set(cache_key, response.model_dump())

        return response
