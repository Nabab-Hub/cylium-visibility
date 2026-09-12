from typing import Optional
from pydantic import BaseModel, Field, model_validator


class ImageInputRequest(BaseModel):
    """
    Standard request schema for image processing endpoints.
    Exactly one of image_base64, image_url, or image_path should be provided.
    """
    image_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded image string (with or without data URI prefix like data:image/jpeg;base64,...)"
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Publicly accessible HTTP/HTTPS URL of the image"
    )
    image_path: Optional[str] = Field(
        default=None,
        description="Absolute or relative local file path to the image on the server"
    )

    @model_validator(mode="after")
    def check_at_least_one_source(self):
        provided = [
            bool(self.image_base64),
            bool(self.image_url),
            bool(self.image_path),
        ]
        if sum(provided) == 0:
            raise ValueError(
                "At least one image source must be provided: 'image_base64', 'image_url', or 'image_path'."
            )
        if sum(provided) > 1:
            raise ValueError(
                "Please provide only ONE of 'image_base64', 'image_url', or 'image_path'."
            )
        return self


class ErrorResponse(BaseModel):
    """Standardized API error response format."""
    detail: str = Field(..., description="Description of the error")
    error_code: Optional[str] = Field(default=None, description="Application error identifier")


class HealthResponse(BaseModel):
    """Health check status response."""
    status: str = Field(..., description="System health status (healthy/degraded)")
    version: str = Field(..., description="API Version")
    gemini_configured: bool = Field(..., description="Whether Gemini API key is configured")
    firebase_connected: bool = Field(default=False, description="Whether Firebase Firestore is connected")
    visibility_model: str = Field(..., description="Configured Gemini vision model")
