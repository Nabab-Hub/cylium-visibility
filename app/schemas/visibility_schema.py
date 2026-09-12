from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.common_schema import ImageInputRequest


class VisibilityRequest(ImageInputRequest):
    """Request payload for /detect-visibility endpoint."""
    pass


class GeminiVisibilityRawOutput(BaseModel):
    """Structured JSON schema requested from Gemini Vision model."""
    object_name: str = Field(
        description="Name of the prominent object detected in the image (e.g. 'Water Bottle', 'Apple', 'Sneaker', or 'Unknown')"
    )
    visibility: bool = Field(
        description="True if the main object is clearly, sharply, and adequately visible. False if blurry, occluded, cut off, or indistinct."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 regarding the visibility and identification assessment."
    )
    message: str = Field(
        description="Clear explanation of the visibility status and reasoning."
    )
    is_blurry: Optional[bool] = Field(
        default=None,
        description="Whether the object or scene suffers from significant blur."
    )
    is_occluded: Optional[bool] = Field(
        default=None,
        description="Whether the object is partially obstructed or hidden behind something."
    )
    is_cut_off: Optional[bool] = Field(
        default=None,
        description="Whether the object is cropped or cut off by the image boundary."
    )


class VisibilityResponse(BaseModel):
    """Public response model for /detect-visibility endpoint."""
    object_name: str = Field(
        ...,
        description="Identified primary object in the image or 'Unknown'"
    )
    visibility: bool = Field(
        ...,
        description="Whether the object is clearly visible and of acceptable quality"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detection and quality confidence score"
    )
    message: str = Field(
        ...,
        description="Detailed explanation of the object visibility and quality"
    )
    is_blurry: Optional[bool] = Field(
        default=None,
        description="Visual blur indicator"
    )
    is_occluded: Optional[bool] = Field(
        default=None,
        description="Object occlusion indicator"
    )
    is_cut_off: Optional[bool] = Field(
        default=None,
        description="Object cropping indicator"
    )
    blur_score: Optional[float] = Field(
        default=None,
        description="OpenCV Laplacian variance sharpness/blur score (higher = sharper, typically > 100)"
    )
    cached: bool = Field(
        default=False,
        description="Whether this result was served from the in-memory cache"
    )
