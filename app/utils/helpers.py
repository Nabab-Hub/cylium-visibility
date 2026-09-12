import hashlib
import time
from typing import Optional


def hash_api_key(api_key: str) -> str:
    """
    Converts raw API key into SHA-256 hex string for Firestore `apiKeys` lookup.
    Example: cyl_live_xxxx -> 8cd2c46e0ea3827...
    """
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def current_timestamp_ms() -> int:
    """Returns current UTC timestamp in milliseconds."""
    return int(time.time() * 1000)
