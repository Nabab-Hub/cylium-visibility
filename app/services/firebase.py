import os
import json
import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import HTTPException

from app.config import settings
from app.utils.helpers import current_timestamp_ms

logger = logging.getLogger("visibility.firebase")

_firestore_client: Optional[firestore.Client] = None
_firebase_initialized: bool = False

DEFAULT_CREDENTIAL_PATHS = [
    "/etc/secrets/firebase-service-account.json",
    "firebase-service-account.json",
    "nude-checker-firebase-adminsdk.json",
    os.path.join(os.path.dirname(__file__), "..", "..", "nude-checker-firebase-adminsdk.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "firebase-service-account.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "nsfw-content-checker-api", "nude-checker-firebase-adminsdk.json"),
    os.path.join(os.getcwd(), "nude-checker-firebase-adminsdk.json"),
    os.path.join(os.getcwd(), "firebase-service-account.json"),
    os.path.join(os.getcwd(), "ai-models", "visibility-model", "nude-checker-firebase-adminsdk.json"),
    os.path.join(os.getcwd(), "ai-models", "nsfw-content-checker-api", "nude-checker-firebase-adminsdk.json"),
    os.path.join(os.getcwd(), "..", "..", "firebase-service-account.json"),
]


def get_firestore_client() -> Optional[firestore.Client]:
    """
    Get or initialize the Firestore client singleton.
    Supports inline JSON, file paths, or Application Default Credentials.
    """
    global _firestore_client, _firebase_initialized

    if _firestore_client is not None:
        return _firestore_client

    # 1. Inline JSON
    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        try:
            cert_dict = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
            cred = credentials.Certificate(cert_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            _firestore_client = firestore.client()
            logger.info("Firebase initialized using inline service account JSON.")
            return _firestore_client
        except Exception as exc:
            logger.warning("Failed to initialize Firebase from inline JSON: %s", exc)

    # 2. File path credentials
    candidate_paths = [settings.FIREBASE_CREDENTIALS, os.getenv("FIREBASE_CREDENTIALS")] + DEFAULT_CREDENTIAL_PATHS

    for path in candidate_paths:
        if path and os.path.exists(path):
            try:
                cred = credentials.Certificate(path)
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                _firestore_client = firestore.client()
                logger.info("Firebase initialized from certificate: %s", path)
                return _firestore_client
            except Exception as exc:
                logger.warning("Failed to initialize Firebase from certificate %s: %s", path, exc)

    # 3. ADC if environment variable set
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={"projectId": settings.FIREBASE_PROJECT_ID})
            _firebase_initialized = True
            _firestore_client = firestore.client()
            logger.info("Firebase initialized via ADC with project: %s", settings.FIREBASE_PROJECT_ID)
            return _firestore_client
        except Exception as exc:
            logger.warning("Could not initialize Firebase via ADC: %s", exc)

    return None


def is_firebase_connected() -> bool:
    """Checks whether Firestore client is initialized and reachable."""
    return get_firestore_client() is not None


@firestore.transactional
def _increment_usage_transaction(transaction, key_ref):
    """
    Atomically increments requestCount inside a Firestore transaction.
    Enforces monthly limits.
    """
    snapshot = key_ref.get(transaction=transaction)

    if not snapshot.exists:
        raise RuntimeError("API key disappeared during request")

    data = snapshot.to_dict() or {}
    current_count = int(data.get("requestCount", 0))
    monthly_limit = int(data.get("monthlyLimit", 0))

    if monthly_limit > 0 and current_count >= monthly_limit:
        raise RuntimeError("MONTHLY_LIMIT_REACHED")

    transaction.update(
        key_ref,
        {
            "requestCount": current_count + 1,
        },
    )


def increment_usage(key_ref) -> None:
    """
    Executes the Firestore transaction to increment request count.
    """
    if key_ref is None:
        return

    db = get_firestore_client()
    if db is None:
        return

    transaction = db.transaction()
    try:
        _increment_usage_transaction(transaction, key_ref)
    except RuntimeError as exc:
        if str(exc) == "MONTHLY_LIMIT_REACHED":
            raise HTTPException(
                status_code=429,
                detail={
                    "success": False,
                    "error": "monthly_limit_reached",
                    "message": "Monthly API request limit reached. Please upgrade your plan.",
                },
            )
        raise


def log_usage(
    user_id: Optional[str],
    key_id: Optional[str],
    endpoint: str = "/detect-visibility",
    status_code: int = 200,
) -> None:
    """
    Logs usage entry to `usageLogs` collection matching the CyliumOS dashboard schema.
    """
    try:
        db = get_firestore_client()
        if db is None:
            return

        db.collection("usageLogs").add(
            {
                "userId": user_id or "",
                "keyId": key_id or "",
                "timestamp": current_timestamp_ms(),
                "endpoint": endpoint,
                "statusCode": status_code,
            }
        )
    except Exception as exc:
        logger.warning("Failed to write usage log to Firestore: %s", exc)
