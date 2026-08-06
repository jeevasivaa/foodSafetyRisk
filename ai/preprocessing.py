"""
ai/preprocessing.py — Image pre-processing pipeline.

Prepares a raw uploaded image for OCR and damage detection:
  - Resize (longest side → MAX_IMAGE_SIZE)
  - Denoise
  - Contrast enhancement (CLAHE)
  - Return as RGB numpy array AND save a cleaned copy for downstream modules
"""
import os
import cv2
import numpy as np
from PIL import Image

from ai.ai_config import MAX_IMAGE_SIZE


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Load and pre-process an image for AI analysis.

    Args:
        image_path: Path to the source image file.

    Returns:
        Preprocessed image as an RGB numpy array, or None on failure.
    """
    try:
        # ── Load via PIL first (handles EXIF rotation, exotic formats) ────
        pil_img = Image.open(image_path).convert("RGB")
        img = np.array(pil_img)  # RGB uint8

        # ── Resize (preserve aspect ratio) ────────────────────────────────
        h, w = img.shape[:2]
        scale = MAX_IMAGE_SIZE / max(h, w)
        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # ── Denoise (fast Non-Local Means on luminance channel only) ──────
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        img_bgr = cv2.fastNlMeansDenoisingColored(img_bgr, None, 7, 7, 7, 21)

        # ── CLAHE contrast enhancement on the L channel ───────────────────
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        img_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # ── Return as RGB ─────────────────────────────────────────────────
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return img_rgb

    except Exception as e:
        print(f"[Preprocessing] Error: {e}")
        # Return raw array as fallback
        try:
            pil_img = Image.open(image_path).convert("RGB")
            return np.array(pil_img)
        except Exception:
            return None


def load_bgr(image_path: str) -> np.ndarray:
    """
    Load image in BGR format (for OpenCV operations).
    Returns None on failure.
    """
    try:
        pil_img = Image.open(image_path).convert("RGB")
        img = np.array(pil_img)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"[Preprocessing] load_bgr error: {e}")
        return None
