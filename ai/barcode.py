"""
ai/barcode.py — Barcode detection using pyzbar.

Tries multiple image variants (original, grayscale, sharpened) to maximise
detection rate on real-world product photos.
"""
import cv2
import numpy as np

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_AVAILABLE = True
except Exception:
    pyzbar_decode = None
    PYZBAR_AVAILABLE = False
    print("[Barcode] pyzbar not available (missing DLL or import error) — barcode detection disabled.")

from ai.preprocessing import load_bgr


def detect_barcode(image_path: str) -> dict:
    """
    Detect a barcode / QR code in the product image.

    Args:
        image_path: Path to the uploaded product image.

    Returns:
        dict with keys:
            number (str): Barcode data string or "Not Detected"
            type   (str): Barcode symbology (e.g. "EAN13") or ""
    """
    _default = {"number": "Not Detected", "type": ""}

    if not PYZBAR_AVAILABLE:
        return _default

    try:
        img_bgr = load_bgr(image_path)
        if img_bgr is None:
            return _default

        # Try a sequence of increasingly aggressive pre-processing passes
        candidates = _generate_candidates(img_bgr)

        for candidate in candidates:
            decoded = pyzbar_decode(candidate)
            if decoded:
                best = decoded[0]
                data = best.data.decode("utf-8", errors="replace").strip()
                btype = best.type if best.type else ""
                if data:
                    return {"number": data, "type": btype}

        return _default

    except Exception as e:
        print(f"[Barcode] Error: {e}")
        return _default


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_candidates(img_bgr: np.ndarray) -> list:
    """
    Return a list of image variants to try for barcode detection.
    pyzbar works best with clean, high-contrast grayscale images.
    """
    candidates = []

    # 1. Raw grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    candidates.append(gray)

    # 2. Sharpened grayscale
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp = cv2.filter2D(gray, -1, kernel)
    candidates.append(sharp)

    # 3. Adaptive threshold (helps with bad lighting)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    candidates.append(thresh)

    # 4. Upscaled (for small barcodes)
    h, w = img_bgr.shape[:2]
    if max(h, w) < 800:
        scale = 800 / max(h, w)
        up_gray = cv2.resize(gray, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_CUBIC)
        candidates.append(up_gray)

    # 5. Original BGR (pyzbar can handle colour images too)
    candidates.append(img_bgr)

    return candidates
