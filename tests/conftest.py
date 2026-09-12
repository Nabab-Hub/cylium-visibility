import io
import base64
import pytest
from PIL import Image, ImageDraw, ImageFilter
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import verify_api_key
from app.services.cache_service import cache_service


@pytest.fixture(autouse=True)
def clear_cache():
    """Ensures in-memory cache is empty before each test."""
    cache_service.clear()


@pytest.fixture(autouse=True)
def mock_auth_dependency():
    """Default dependency override allowing route tests to run without Firestore writes."""
    app.dependency_overrides[verify_api_key] = lambda: {
        "key_id": "test_key_id",
        "key_ref": None,
        "key_hash": "test_hash",
        "user_id": "test_user_id",
        "plan": "pro",
        "key_prefix": "nsk_live",
        "created_at": 1700000000000,
        "expires_at": None,
        "monthly_limit": 1000,
        "request_count": 5,
        "status": "active",
    }
    yield
    app.dependency_overrides.pop(verify_api_key, None)


@pytest.fixture
def sample_sharp_image_bytes() -> bytes:
    """Generates a high-contrast sharp checkerboard image."""
    img = Image.new("RGB", (200, 200), color="white")
    draw = ImageDraw.Draw(img)
    for x in range(0, 200, 20):
        for y in range(0, 200, 20):
            if (x // 20 + y // 20) % 2 == 0:
                draw.rectangle([x, y, x + 20, y + 20], fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_blurry_image_bytes(sample_sharp_image_bytes) -> bytes:
    """Generates a heavily blurred image."""
    img = Image.open(io.BytesIO(sample_sharp_image_bytes))
    blurred = img.filter(ImageFilter.GaussianBlur(radius=15))
    buf = io.BytesIO()
    blurred.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_base64_sharp(sample_sharp_image_bytes) -> str:
    """Base64 string of the sharp test image."""
    return base64.b64encode(sample_sharp_image_bytes).decode("utf-8")


@pytest.fixture
def sample_data_uri_sharp(sample_sharp_image_bytes) -> str:
    """Data URI format of the sharp test image."""
    b64 = base64.b64encode(sample_sharp_image_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient instance."""
    return TestClient(app)
