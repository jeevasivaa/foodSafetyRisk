"""
ai/analyzer.py — AI Placeholder Module
---------------------------------------
Phase 1: Returns dummy analysis data.
Phase 2: Replace the body of analyze_product() with EasyOCR + YOLO logic.
         No Flask routes need to change — they always call analyze_product(image_path).
"""


def analyze_product(image_path: str) -> dict:
    """
    Analyze a food package image.

    Args:
        image_path (str): Absolute or relative path to the uploaded product image.

    Returns:
        dict: Analysis results with the following keys:
            - expiry_date         (str)
            - manufacturing_date  (str)
            - package_condition   (str)  e.g. 'Good' | 'Fair' | 'Poor'
            - damage_percentage   (str)  e.g. '0%'
            - barcode             (str)  e.g. 'Detected' | 'Not Detected'
            - quality_score       (str)  0–100 numeric string
            - status              (str)  'Safe' | 'Warning' | 'Unsafe'

    TODO (Phase 2):
        1. Load image from image_path using cv2 or PIL.
        2. Run YOLO model to detect package damage and barcode regions.
        3. Run EasyOCR on detected regions to extract expiry/manufacturing dates.
        4. Compute quality_score from damage_percentage and date validity.
        5. Return the same dict structure — routes require no changes.
    """
    # ── Phase 1 Placeholder ─────────────────────────────────────────────────
    return {
        "expiry_date":          "31-12-2026",
        "manufacturing_date":   "01-01-2026",
        "package_condition":    "Good",
        "damage_percentage":    "0%",
        "barcode":              "Detected",
        "quality_score":        "95",
        "status":               "Safe",
    }
    # ── End Placeholder ──────────────────────────────────────────────────────
