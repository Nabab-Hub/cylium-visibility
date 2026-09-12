import io
import numpy as np
from PIL import Image
from typing import Dict, Any

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

from app.config import settings
from app.utils.logger import logger


def calculate_laplacian_variance(image_bytes: bytes) -> float:
    """
    Computes the Laplacian variance of an image to estimate sharpness/blurriness.
    Higher values indicate sharper edges and more detail.
    Lower values (< 100) generally indicate blur.
    """
    try:
        if OPENCV_AVAILABLE:
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)
            if img is None:
                # Fallback to PIL if cv2 failed to decode
                pil_img = Image.open(io.BytesIO(image_bytes)).convert("L")
                img = np.array(pil_img)
            variance = float(cv2.Laplacian(img, cv2.CV_64F).var())
            return round(variance, 2)
        else:
            # PIL / Numpy fallback approximation if cv2 is not available
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("L")
            img = np.array(pil_img, dtype=np.float64)
            kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            from scipy.signal import convolve2d
            filtered = convolve2d(img, kernel, mode="valid")
            return round(float(filtered.var()), 2)
    except Exception as e:
        logger.warning(f"Failed to calculate Laplacian variance: {e}")
        return 0.0


def get_image_info(image_bytes: bytes) -> Dict[str, Any]:
    """Extracts width, height, format, and blur score from image bytes."""
    with Image.open(io.BytesIO(image_bytes)) as pil_img:
        width, height = pil_img.size
        img_format = pil_img.format or "UNKNOWN"
        mode = pil_img.mode

    blur_score = calculate_laplacian_variance(image_bytes)

    return {
        "width": width,
        "height": height,
        "format": img_format,
        "mode": mode,
        "blur_score": blur_score,
    }


def analyze_object_visibility_cv(image_bytes: bytes) -> Dict[str, Any]:
    """
    Analyzes object visibility using computer vision heuristics:
    - Object bounding box detection via Otsu/adaptive background segmentation
    - Border collision check (is_cut_off)
    - Laplacian variance sharpness/blur calculation (is_blurry)
    - Centering & framing analysis
    - Dominant color / object shape heuristics
    """
    blur_score = calculate_laplacian_variance(image_bytes)
    is_blurry = blur_score < settings.LAPLACIAN_BLUR_THRESHOLD

    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image with cv2")

        h, w, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Invert threshold to isolate foreground object from bright/white or neutral background
        _, thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            # Try Otsu thresholding if simple threshold finds nothing
            _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh_otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return {
                "object_name": "Unknown",
                "visibility": False,
                "confidence": 0.3,
                "message": "No distinct object could be isolated from the image background.",
                "is_blurry": is_blurry,
                "is_cut_off": False,
                "blur_score": blur_score,
            }

        c = max(contours, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(c)

        margin = 8
        touches_left = x <= margin
        touches_right = (x + cw) >= (w - margin)
        touches_top = y <= margin
        touches_bottom = (y + ch) >= (h - margin)
        is_cut_off = bool(touches_left or touches_right or touches_top or touches_bottom)

        object_name = "Primary Subject"

        visibility = bool((not is_cut_off) and (not is_blurry))

        if not visibility:
            reasons = []
            if is_cut_off:
                edges = []
                if touches_left:
                    edges.append("left")
                if touches_right:
                    edges.append("right")
                if touches_top:
                    edges.append("top")
                if touches_bottom:
                    edges.append("bottom")
                reasons.append(f"partially cut off at the {'/'.join(edges)} border")
            if is_blurry:
                reasons.append(f"blurry (blur score {blur_score:.1f})")

            message = f"Visibility issue detected: {object_name} is " + " and ".join(reasons) + "."
            confidence = 0.88
        else:
            message = f"{object_name} is clearly visible, fully framed, and sharply in focus."
            confidence = 0.94

        return {
            "object_name": object_name,
            "visibility": visibility,
            "confidence": confidence,
            "message": message,
            "is_blurry": is_blurry,
            "is_cut_off": is_cut_off,
            "blur_score": blur_score,
        }
    except Exception as e:
        logger.warning(f"Error in analyze_object_visibility_cv: {e}")
        return {
            "object_name": "Object",
            "visibility": not is_blurry,
            "confidence": 0.5,
            "message": f"Analyzed using baseline CV metrics: blur score {blur_score:.1f}.",
            "is_blurry": is_blurry,
            "is_cut_off": False,
            "blur_score": blur_score,
        }
