from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Configuration
    PROJECT_NAME: str = "Object Visibility & Quality Detection API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = ""
    PORT: int = 8003
    DEBUG: bool = False

    # Gemini Vision API Credentials & Model
    GEMINI_API_KEY: str = ""
    VISIBILITY_MODEL: str = "gemini-3.6-flash"

    # Firebase Firestore Configuration (API Key validation & Usage tracking)
    FIREBASE_PROJECT_ID: str = "cyliumos"
    FIREBASE_CREDENTIALS: Optional[str] = "cyliumos-firebase-adminsdk.json"
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = None
    REQUIRE_FIREBASE_AUTH: bool = True

    # Legacy static key fallback (if Firebase is disabled)
    API_KEY: Optional[str] = None

    # Rate Limiting (SlowAPI)
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # Image Processing & Validation
    MAX_IMAGE_SIZE_MB: int = 10
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    LAPLACIAN_BLUR_THRESHOLD: float = 100.0
    ALLOWED_IMAGE_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    ]

    # In-memory Cache Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    CACHE_MAX_ENTRIES: int = 1000


settings = Settings()
