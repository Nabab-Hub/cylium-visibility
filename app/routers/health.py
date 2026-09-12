from fastapi import APIRouter
from app.schemas.common_schema import HealthResponse
from app.services.gemini_client import gemini_client_wrapper
from app.services.firebase import is_firebase_connected
from app.config import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check and service status",
    description="Returns microservice health status, version, Gemini vision configuration, and Firebase status.",
)
async def health_check() -> HealthResponse:
    conn_info = gemini_client_wrapper.check_connection()
    firebase_ok = is_firebase_connected()
    gemini_ok = conn_info.get("configured", False)

    # If Firebase auth is mandatory, system is healthy only when both are ready
    if settings.REQUIRE_FIREBASE_AUTH:
        is_healthy = gemini_ok and firebase_ok
    else:
        is_healthy = gemini_ok

    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        version=settings.VERSION,
        gemini_configured=gemini_ok,
        firebase_connected=firebase_ok,
        visibility_model=settings.VISIBILITY_MODEL,
    )
