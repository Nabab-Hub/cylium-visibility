# 🔍 Object Visibility & Image Quality Detection Microservice

A production-grade, high-performance computer vision microservice powered by **Google Gemini Vision** (`google-genai`), **OpenCV**, and **Firebase Firestore** for unified API key authentication, quota enforcement, and usage tracking.

This service analyzes an image to determine whether a central product or subject is clearly and acceptably visible, in focus, centered, uncropped, and unobstructed.

---

## 🌟 Key Features

- **Multimodal AI Vision Analysis**: Uses Google Gemini Vision (`gemini-3.6-flash`, `gemini-2.5-flash`, etc.) with strict, type-safe JSON schema output.
- **OpenCV Blur & Sharpness Telemetry**: Objective Laplacian variance calculation for precise focus, lens blur, and optical quality assessment.
- **Automated Diagnostic Flags**:
  - `visibility`: Primary boolean indicating whether the object is clearly and acceptably visible.
  - `is_blurry`: Flags optical, motion, or lens blur.
  - `is_occluded`: Flags partial or full object obstruction.
  - `is_cut_off`: Flags objects cut off or cropped at frame margins.
  - `confidence`: Calibrated confidence score between `0.0` and `1.0`.
  - `blur_score`: Floating-point sharpness metric (Laplacian variance).
- **Universal Ingestion Methods**:
  - Base64 string (plain or Data URI)
  - Public HTTP/HTTPS image URL
  - Local server file path
  - Direct `multipart/form-data` binary upload
- **Firebase Firestore Integration**:
  - Validates client `X-API-Key` headers against the shared Firestore `apiKeys` collection (SHA-256 hashed).
  - Enforces status (`active`, `revoked`, `expired`) and monthly quota limits (`requestCount` vs `monthlyLimit`).
  - Atomically increments usage count on each completed request.
  - Automatically records usage metadata into the `usageLogs` collection.
- **In-Memory TTL Caching**: SHA-256 hash-based deduplication for sub-millisecond cached responses.
- **Production Ready**: Built-in health checks (`/health`), SlowAPI rate limiting, Docker containerization, and 100% test coverage.

---

## 📁 Project Structure

```
visibility-model/
├── .dockerignore            # Docker build ignore patterns
├── .env                     # Local environment variables
├── .env.example             # Template environment variables
├── .gitignore               # Git ignore patterns (ignores keys & caches)
├── Dockerfile               # Production Docker container definition
├── docker-compose.yml       # One-command Docker Compose orchestration
├── requirements.txt         # Python dependencies
├── README.md                # Microservice documentation
├── samples/                 # Sample images for testing
│   ├── test_img1.jpg        # Edge-cropped / cut-off test image
│   ├── test_img2.jpg        # Centered & sharp test image
│   └── Banana-Single.jpg
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization, lifespan & routes
│   ├── config.py            # Pydantic Settings & environment variables
│   ├── api/
│   │   ├── __init__.py
│   │   └── deps.py          # Firestore verify_api_key authentication dependency
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py        # GET /health endpoint (Gemini + Firebase status)
│   │   └── visibility.py    # POST /detect-visibility & POST /detect-visibility/upload
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common_schema.py # Common request, error, and health models
│   │   └── visibility_schema.py # Request & response models for visibility
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cache_service.py # In-memory TTL LRU cache
│   │   ├── firebase.py      # Firestore client, atomic usage counter & logging
│   │   ├── gemini_client.py # Google GenAI SDK wrapper with retry logic
│   │   ├── image_loader.py  # Ingestion from base64, URL, path, or upload
│   │   └── visibility_service.py # Inspection orchestrator & JSON parser
│   └── utils/
│       ├── __init__.py
│       ├── cv_utils.py      # OpenCV Laplacian variance & contour analysis
│       ├── helpers.py       # SHA-256 key hashing & timestamp utilities
│       ├── logger.py        # Structured logging setup
│       └── validators.py    # Payload size & image format validation
└── tests/
    ├── __init__.py
    ├── conftest.py          # Pytest fixtures and mock images
    ├── test_firebase_auth.py# Firebase Firestore authentication & quota tests
    ├── test_health.py       # Health check tests
    ├── test_image_loader.py # Ingestion unit tests
    ├── test_validators.py   # Blur score and validator tests
    └── test_visibility.py   # Visibility endpoint integration tests
```

---

## ⚙️ Environment Configuration (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key from [Google AI Studio](https://aistudio.google.com/). |
| `VISIBILITY_MODEL` | No | `gemini-3.6-flash` | Gemini vision model candidate (`gemini-3.6-flash`, `gemini-2.5-flash`). |
| `FIREBASE_PROJECT_ID` | No | `nude-checker` | Firebase Project ID. |
| `FIREBASE_CREDENTIALS` | No | `nude-checker-firebase-adminsdk.json` | Path to service account JSON file. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | No | `""` | Optional raw JSON string for cloud/container deployment. |
| `REQUIRE_FIREBASE_AUTH` | No | `true` | Enforce Firestore API key authentication on detection endpoints. |
| `API_KEY` | No | `""` | Optional static key fallback if Firebase is disabled. |
| `RATE_LIMIT_DEFAULT` | No | `60/minute` | Rate limit per client IP via SlowAPI. |
| `MAX_IMAGE_SIZE_MB` | No | `10` | Maximum allowed image file size in MB. |
| `CACHE_ENABLED` | No | `true` | Enables in-memory TTL caching for duplicate image hashes. |
| `CACHE_TTL_SECONDS` | No | `3600` | In-memory cache duration in seconds. |
| `DEBUG` | No | `false` | Enables verbose debug logging. |

---

## 🔑 Authentication Architecture

All detection endpoints require an active API key passed in the **`X-API-Key`** header:

```http
X-API-Key: cyl_live_x9z0abcdef1234567890
```

### Firestore Verification Workflow
1. The raw API key is hashed using **SHA-256**.
2. The `apiKeys` collection is queried for `keyHash == <hash>`.
3. The key's metadata is verified:
   - **Status**: Must equal `'active'`.
   - **Expiration**: `expiresAt` (Unix ms) must be greater than current UTC time (if set).
   - **Monthly Quota**: `requestCount` must be strictly less than `monthlyLimit` (when `monthlyLimit > 0`).
4. On successful analysis:
   - `requestCount` is atomically incremented by `1` using a Firestore transaction.
   - An entry is logged to `usageLogs`:
     ```json
     {
       "userId": "usr_9812",
       "keyId": "doc_id_xyz",
       "timestamp": 1726077000000,
       "endpoint": "/detect-visibility",
       "statusCode": 200
     }
     ```

---

## 📡 API Endpoints Reference

### 1. Health & Readiness Check (`GET /health`)
Returns microservice health, version, Gemini vision configuration, and Firebase connectivity.

#### Request:
```bash
curl -X GET "http://localhost:8003/health"
```

#### Response (`200 OK`):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "gemini_configured": true,
  "firebase_connected": true,
  "visibility_model": "gemini-3.6-flash"
}
```

---

### 2. Detect Object Visibility via JSON (`POST /detect-visibility`)
Evaluates an image provided via JSON payload. Provide **exactly one** of `image_base64`, `image_url`, or `image_path`.

#### Headers:
| Header | Type | Required | Description |
|---|---|---|---|
| `Content-Type` | string | Yes | `application/json` |
| `X-API-Key` | string | Yes | Valid API key generated from the dashboard |

#### Request Body Schema:
```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "image_url": "https://example.com/product.jpg",
  "image_path": "samples/test_img1.jpg"
}
```

#### cURL Examples:

**A. Using Image URL:**
```bash
curl -X POST "http://localhost:8003/detect-visibility" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cyl_live_x9z0abcdef1234567890" \
  -d '{
    "image_url": "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6"
  }'
```

**B. Using Base64 Data URI:**
```bash
curl -X POST "http://localhost:8003/detect-visibility" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cyl_live_x9z0abcdef1234567890" \
  -d '{
    "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQE..."
  }'
```

#### Response (`200 OK`):
```json
{
  "object_name": "Red Apple",
  "visibility": true,
  "confidence": 0.98,
  "message": "The apple is centrally positioned, well-lit, sharp, and clearly visible.",
  "is_blurry": false,
  "is_occluded": false,
  "is_cut_off": false,
  "blur_score": 312.4,
  "cached": false
}
```

---

### 3. Detect Object Visibility via File Upload (`POST /detect-visibility/upload`)
Evaluates an image uploaded directly as binary `multipart/form-data`.

#### Headers:
| Header | Type | Required | Description |
|---|---|---|---|
| `Content-Type` | string | Yes | `multipart/form-data` |
| `X-API-Key` | string | Yes | Valid API key |

#### cURL Example:
```bash
curl -X POST "http://localhost:8003/detect-visibility/upload" \
  -H "X-API-Key: cyl_live_x9z0abcdef1234567890" \
  -F "file=@samples/test_img1.jpg"
```

#### Response (`200 OK`):
```json
{
  "object_name": "Checkerboard Pattern",
  "visibility": false,
  "confidence": 0.95,
  "message": "The pattern is sharp and in focus, but cropped and cut off at the right frame border.",
  "is_blurry": false,
  "is_occluded": false,
  "is_cut_off": true,
  "blur_score": 284.15,
  "cached": false
}
```

---

## 💻 SDK & Code Integration Examples

### JavaScript / TypeScript (Fetch API)

```typescript
async function detectVisibility(imageUrl: string, apiKey: string) {
  const response = await fetch("http://localhost:8003/detect-visibility", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify({ image_url: imageUrl }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(`[${response.status}] ${err.message || err.error || "Visibility detection failed"}`);
  }

  const result = await response.json();
  console.log(`Object: ${result.object_name}`);
  console.log(`Visible: ${result.visibility} (Confidence: ${(result.confidence * 100).toFixed(1)}%)`);
  console.log(`Blur: ${result.is_blurry}, Occluded: ${result.is_occluded}, Cropped: ${result.is_cut_off}`);
  return result;
}

// Example usage
detectVisibility("https://example.com/item.png", "cyl_live_x9z0abcdef1234567890")
  .then(console.log)
  .catch(console.error);
```

### Python (`requests`)

```python
import requests

API_URL = "http://localhost:8003/detect-visibility/upload"
API_KEY = "cyl_live_x9z0abcdef1234567890"

headers = {
    "X-API-Key": API_KEY,
}

with open("samples/test_img1.jpg", "rb") as f:
    files = {"file": ("test_img1.jpg", f, "image/jpeg")}
    response = requests.post(API_URL, headers=headers, files=files)

if response.status_code == 200:
    data = response.json()
    print(f"Object: {data['object_name']}")
    print(f"Visible: {data['visibility']}")
    print(f"Confidence: {data['confidence']:.2f}")
    print(f"Diagnostics: is_blurry={data['is_blurry']}, is_cut_off={data['is_cut_off']}")
    print(f"Explanation: {data['message']}")
else:
    print(f"Error {response.status_code}:", response.json())
```

---

## 🚨 Error Codes & Troubleshooting

All error responses adhere to standard HTTP status codes and provide a consistent JSON error schema:

```json
{
  "success": false,
  "error": "error_identifier_code",
  "message": "Human readable explanation of the error"
}
```

### Error Summary Table

| HTTP Status | Error Code (`error`) | Description & Trigger | Resolution |
|---|---|---|---|
| **`400 Bad Request`** | `invalid_image` | Image data is corrupted, empty, or unreadable by OpenCV. | Verify the image format and base64 encoding integrity. |
| **`400 Bad Request`** | `empty_image` | Image buffer length is 0 bytes. | Supply a non-empty image file or payload. |
| **`401 Unauthorized`** | `missing_api_key` | `X-API-Key` header was omitted from the request. | Provide a valid `X-API-Key` header. |
| **`401 Unauthorized`** | `invalid_api_key` | Key not found in Firestore `apiKeys` collection. | Check key spelling or generate a new key from dashboard. |
| **`403 Forbidden`** | `api_key_inactive` | Key exists but status is `'revoked'`. | Reactivate the key or generate a replacement. |
| **`403 Forbidden`** | `api_key_expired` | Key has exceeded its `expiresAt` timestamp. | Renew subscription or extend expiration timestamp. |
| **`413 Payload Too Large`**| `image_too_large` | Image exceeds `MAX_IMAGE_SIZE_MB` (default 10 MB). | Compress or resize image before uploading. |
| **`415 Unsupported Media`**| `unsupported_format` | File MIME type is not JPEG, PNG, WEBP, or HEIC. | Convert image to a supported format (JPEG/PNG/WEBP). |
| **`422 Unprocessable`** | `validation_error` | Missing image source or multiple sources provided in JSON. | Pass exactly ONE of `image_base64`, `image_url`, or `image_path`. |
| **`429 Too Many Requests`**| `monthly_limit_reached`| `requestCount` >= `monthlyLimit`. | Upgrade subscription plan for increased monthly quota. |
| **`429 Too Many Requests`**| `rate_limit_exceeded` | Exceeded IP rate limit (`RATE_LIMIT_DEFAULT`). | Space out requests or contact support for rate limit increase. |
| **`502 Bad Gateway`** | `gemini_api_error` | Google Gemini Vision API returned an error or timeout. | Verify `GEMINI_API_KEY` and check Google Cloud service status. |
| **`503 Unavailable`** | `auth_unavailable` | Firestore client cannot connect to database. | Verify Firebase credentials JSON and network egress. |

---

### Error Response Samples

#### 1. Missing API Key (`401 Unauthorized`)
```json
{
  "success": false,
  "error": "missing_api_key",
  "message": "X-API-Key header is required"
}
```

#### 2. Invalid API Key (`401 Unauthorized`)
```json
{
  "success": false,
  "error": "invalid_api_key",
  "message": "Invalid API key"
}
```

#### 3. Inactive / Revoked Key (`403 Forbidden`)
```json
{
  "success": false,
  "error": "api_key_inactive",
  "message": "API key is not active (status: revoked)"
}
```

#### 4. Monthly Quota Reached (`429 Too Many Requests`)
```json
{
  "success": false,
  "error": "monthly_limit_reached",
  "message": "Monthly API request limit reached. Please upgrade your plan."
}
```

---

## 🏃 Running Locally

### 1. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Set GEMINI_API_KEY, FIREBASE_PROJECT_ID, and FIREBASE_CREDENTIALS
```

### 4. Start Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

---

## 🐳 Running with Docker

### Option A: Using Docker Compose
```bash
docker compose up -d --build
```

### Option B: Using Plain Docker
```bash
docker build -t visibility-model:latest .
docker run -d \
  --name visibility-api \
  -p 8003:8003 \
  --env-file .env \
  visibility-model:latest
```

---

## 🧪 Automated Testing

Run the complete Pytest suite inside `visibility-model`:

```bash
pytest tests/ -v
```

All 21 unit and integration tests will execute and pass:

```
tests/test_firebase_auth.py::test_missing_api_key_returns_401 PASSED     [  4%]
tests/test_firebase_auth.py::test_invalid_api_key_returns_401 PASSED     [  9%]
tests/test_firebase_auth.py::test_inactive_api_key_raises_403 PASSED     [ 14%]
tests/test_firebase_auth.py::test_monthly_limit_reached_raises_429 PASSED [ 19%]
tests/test_firebase_auth.py::test_valid_active_key_returns_metadata PASSED [ 23%]
tests/test_health.py::test_health_check_endpoint PASSED                  [ 28%]
tests/test_health.py::test_root_endpoint PASSED                          [ 33%]
tests/test_image_loader.py::test_load_from_base64_plain PASSED           [ 38%]
tests/test_image_loader.py::test_load_from_base64_data_uri PASSED        [ 42%]
tests/test_image_loader.py::test_load_from_base64_invalid PASSED         [ 47%]
tests/test_image_loader.py::test_load_from_path_missing PASSED           [ 52%]
tests/test_validators.py::test_validate_image_bytes_valid PASSED         [ 57%]
tests/test_validators.py::test_validate_image_bytes_empty PASSED         [ 61%]
tests/test_validators.py::test_validate_image_bytes_corrupt PASSED       [ 66%]
tests/test_validators.py::test_laplacian_variance_sharp_vs_blurry PASSED [ 71%]
tests/test_validators.py::test_get_image_info PASSED                     [ 76%]
tests/test_visibility.py::test_detect_visibility_json_success PASSED     [ 80%]
tests/test_visibility.py::test_detect_visibility_markdown_fences PASSED  [ 85%]
tests/test_visibility.py::test_detect_visibility_upload_success PASSED   [ 90%]
tests/test_visibility.py::test_detect_visibility_invalid_multiple_sources PASSED [ 95%]
tests/test_visibility.py::test_detect_visibility_no_source PASSED        [100%]

======================== 21 passed in 7.24s ========================
```
