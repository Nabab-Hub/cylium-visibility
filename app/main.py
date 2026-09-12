from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routers import health, visibility
from app.services.firebase import get_firestore_client, is_firebase_connected
from app.services.gemini_client import gemini_client_wrapper
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources and verify service connectivity on startup."""
    logger.info("Initializing %s v%s...", settings.PROJECT_NAME, settings.VERSION)

    # 1. Initialize Firebase
    db = get_firestore_client()
    if db is not None:
        logger.info("✅ Firebase Firestore connected successfully (Project: %s)", settings.FIREBASE_PROJECT_ID)
    else:
        if settings.REQUIRE_FIREBASE_AUTH:
            logger.warning("⚠️ Firebase Firestore credentials not found! Set FIREBASE_CREDENTIALS or provide service account JSON.")
        else:
            logger.info("ℹ️ Running with Firebase authentication disabled.")

    # 2. Check Gemini connection
    gemini_status = gemini_client_wrapper.check_connection()
    if gemini_status.get("configured"):
        logger.info("✅ Gemini Vision client configured (Model: %s)", settings.VISIBILITY_MODEL)
    else:
        logger.warning("⚠️ Gemini API Key not configured. Live detection calls will fail.")

    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)


# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])

# Initialize FastAPI Application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# Object Visibility & Image Quality Detection Microservice

High-performance computer vision microservice powered by **Google Gemini Vision**, **OpenCV**, and **Firebase Firestore Authentication**.

## Authentication:
All detection endpoints require an active API key supplied in the **`X-API-Key`** header.
API keys are validated against the Firestore `apiKeys` collection, enforcing rate limits and monthly quotas.

## Endpoints:
1. 🔍 **`POST /detect-visibility`** — Evaluates object visibility, blur, occlusion, and border cropping from JSON (base64, URL, or local path).
2. 📤 **`POST /detect-visibility/upload`** — Direct multipart/form-data image file upload for visibility and quality inspection.
3. 💓 **`GET /health`** — Service health check, Gemini configuration, and Firebase connection status.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Attach Limiter to App State
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Standardized HTTP exception response."""
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "error_code": f"HTTP_{exc.status_code}"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches all unhandled exceptions."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error_code": "INTERNAL_ERROR"},
    )


# Register Routers
app.include_router(health.router)
app.include_router(visibility.router)


@app.get("/", include_in_schema=False)
async def root():
    """Root metadata response."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "firebase_connected": is_firebase_connected(),
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "/detect-visibility",
            "/detect-visibility/upload",
            "/health",
        ],
    }
