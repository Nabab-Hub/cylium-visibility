from fastapi import APIRouter, UploadFile, File, Depends, status
from app.schemas.visibility_schema import (
    VisibilityRequest,
    VisibilityResponse,
)
from app.schemas.common_schema import ErrorResponse
from app.services.image_loader import ImageLoaderService
from app.services.visibility_service import VisibilityService
from app.services.firebase import increment_usage, log_usage
from app.api.deps import verify_api_key

router = APIRouter(tags=["Visibility Detection"])


@router.post(
    "/detect-visibility",
    response_model=VisibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect object visibility and image quality via JSON",
    description=(
        "Analyzes an image using Google Gemini Vision model to detect whether the main object "
        "(product, fruit, bottle, etc.) is clearly and fully visible, or if it suffers from blur, "
        "partial occlusion, or cropping. Accepts base64 string, image URL, or local file path.\n\n"
        "Requires active API key in `X-API-Key` header."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image payload or missing source"},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
        403: {"model": ErrorResponse, "description": "API key inactive or expired"},
        413: {"model": ErrorResponse, "description": "Image exceeds maximum allowed size"},
        415: {"model": ErrorResponse, "description": "Unsupported image format"},
        429: {"model": ErrorResponse, "description": "Monthly quota limit reached"},
        502: {"model": ErrorResponse, "description": "Gemini API failure"},
    },
)
async def detect_visibility_json(
    request: VisibilityRequest,
    api_key: dict = Depends(verify_api_key),
) -> VisibilityResponse:
    loaded_image = await ImageLoaderService.load_image(
        image_base64=request.image_base64,
        image_url=request.image_url,
        image_path=request.image_path,
    )
    result = await VisibilityService.detect_visibility(loaded_image)

    # Increment usage counter and log to Firestore
    increment_usage(api_key.get("key_ref"))
    log_usage(
        user_id=api_key.get("user_id"),
        key_id=api_key.get("key_id"),
        endpoint="/detect-visibility",
        status_code=200,
    )

    return result


@router.post(
    "/detect-visibility/upload",
    response_model=VisibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect object visibility and image quality via File Upload",
    description=(
        "Upload a direct image file (multipart/form-data) for visibility and quality analysis.\n\n"
        "Requires active API key in `X-API-Key` header."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image payload"},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key"},
        403: {"model": ErrorResponse, "description": "API key inactive or expired"},
        413: {"model": ErrorResponse, "description": "Image exceeds maximum allowed size"},
        415: {"model": ErrorResponse, "description": "Unsupported image format"},
        429: {"model": ErrorResponse, "description": "Monthly quota limit reached"},
        502: {"model": ErrorResponse, "description": "Gemini API failure"},
    },
)
async def detect_visibility_upload(
    file: UploadFile = File(..., description="Image file to analyze (JPEG, PNG, WEBP)"),
    api_key: dict = Depends(verify_api_key),
) -> VisibilityResponse:
    loaded_image = await ImageLoaderService.load_image(upload_file=file)
    result = await VisibilityService.detect_visibility(loaded_image)

    # Increment usage counter and log to Firestore
    increment_usage(api_key.get("key_ref"))
    log_usage(
        user_id=api_key.get("user_id"),
        key_id=api_key.get("key_id"),
        endpoint="/detect-visibility/upload",
        status_code=200,
    )

    return result
