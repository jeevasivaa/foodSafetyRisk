"""
ai/barcode.py — Barcode and QR code detection using pure OpenCV.

Replaces pyzbar to avoid Windows missing-DLL issues (libzbar-64.dll).
Uses cv2.barcode.BarcodeDetector and cv2.QRCodeDetector.
"""
import cv2
import numpy as np
from ai.preprocessing import load_bgr


def detect_barcode(image_path: str) -> dict:
    """
    Detect a barcode / QR code in the product image using OpenCV.

    Args:
        image_path: Path to the uploaded product image.

    Returns:
        dict with keys:
            number (str): Barcode data string or "Not Detected"
            type   (str): Barcode symbology (e.g. "Barcode" or "QR Code") or ""
    """
    _default = {"number": "Not Detected", "type": ""}

    try:
        img_bgr = load_bgr(image_path)
        if img_bgr is None:
            return _default

        # Try a sequence of images (raw, grayscale, sharpened, thresholded)
        candidates = _generate_candidates(img_bgr)

        # 1. Try OpenCV Barcode Detector first
        try:
            barcode_detector = cv2.barcode.BarcodeDetector()
            for candidate in candidates:
                # Returns (ok, decoded_info, decoded_type, corners)
                ok, decoded_info, decoded_type, corners = barcode_detector.detectAndDecode(candidate)
                if ok and decoded_info and len(decoded_info) > 0 and decoded_info[0]:
                    # decoded_info is usually a tuple/list of strings for each detected barcode
                    val = decoded_info[0] if isinstance(decoded_info, (list, tuple)) else decoded_info
                    btype = decoded_type[0] if isinstance(decoded_type, (list, tuple)) else decoded_type
                    
                    # Ensure valid string
                    if val and str(val).strip():
                        return {"number": str(val).strip(), "type": str(btype) if btype else "Barcode"}
        except AttributeError:
            pass # cv2.barcode module not available in this OpenCV version

        # 2. Try OpenCV QR Code Detector as a fallback
        qr_detector = cv2.QRCodeDetector()
        for candidate in candidates:
            val, pts, rect = qr_detector.detectAndDecode(candidate)
            if val and str(val).strip():
                return {"number": str(val).strip(), "type": "QR Code"}

        return _default

    except Exception as e:
        print(f"[Barcode] Error: {e}")
        return _default


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_candidates(img_bgr: np.ndarray) -> list:
    """
    Return a list of image variants to try for detection.
    """
    candidates = []

    # 1. Raw grayscale (usually best for barcodes)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    candidates.append(gray)
    
    # 2. Original BGR
    candidates.append(img_bgr)

    # 3. Sharpened grayscale
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp = cv2.filter2D(gray, -1, kernel)
    candidates.append(sharp)

    # 4. Adaptive threshold (helps with bad lighting)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    candidates.append(thresh)

    return candidates
