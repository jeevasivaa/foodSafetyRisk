"""
ai/analyzer.py — Main AI pipeline entry point.
----------------------------------------------
Phase 2: Real computer vision analysis.

Flask routes call ONLY this function:
    result = analyze_product(image_path)

The returned dict is backwards-compatible with Phase 1 and adds new fields.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from ai.barcode          import detect_barcode
from ai.ocr              import run_ocr
from ai.damage_detection import detect_damage
from ai.quality_score    import calculate_quality_score


_BARCODE_DEFAULT = {"number": "Not Detected", "type": ""}
_OCR_DEFAULT = {
    "expiry_date":        "Not Detected",
    "manufacturing_date": "Not Detected",
    "batch_number":       "Not Detected",
    "mrp":                "Not Detected",
    "net_weight":         "Not Detected",
    "ocr_text":           "",
    "ocr_confidence":     "0",
}
_DAMAGE_DEFAULT = {
    "damage_detected": False,
    "damage_type":     "Package Appears Normal",
    "confidence":      0.0,
    "annotated_image": "",
}


def analyze_product(image_path: str) -> dict:
    """
    Full AI analysis pipeline — Steps 1–3 run in PARALLEL for speed.

    Pipeline:
        ┌─ Step 1: Barcode detection  (OpenCV BarcodeDetector / QRCodeDetector)
        ├─ Step 2: OCR extraction     (EasyOCR)         ← longest step
        └─ Step 3: Damage detection   (OpenCV heuristic)

        → Step 4: Quality scoring     (depends on OCR + damage results)

    Args:
        image_path (str): Absolute path to the uploaded product image.

    Returns:
        dict — all keys from Phase 1 PLUS extended Phase 2 fields.
        Never raises; all failures return safe defaults.
    """
    barcode_result = _BARCODE_DEFAULT.copy()
    ocr_result     = _OCR_DEFAULT.copy()
    damage_result  = _DAMAGE_DEFAULT.copy()

    # ── Steps 1–3 in parallel ─────────────────────────────────────────────
    tasks = {
        "barcode": (detect_barcode, _BARCODE_DEFAULT),
        "ocr":     (run_ocr,        _OCR_DEFAULT),
        "damage":  (detect_damage,  _DAMAGE_DEFAULT),
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_safe_call, fn, image_path, default): key
            for key, (fn, default) in tasks.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            result = future.result()
            if key == "barcode":
                barcode_result = result
            elif key == "ocr":
                ocr_result = result
            elif key == "damage":
                damage_result = result

    # ── Step 4: Quality score (depends on steps 2 & 3) ───────────────────
    quality_result = _safe_call(
        lambda _: calculate_quality_score(ocr_result, damage_result),
        image_path, {
            "quality_score":     "50",
            "status":            "Warning",
            "package_condition": "Fair",
            "recommendation":    "Unable to complete analysis. Please try again.",
            "damage_percentage": "0%",
        }
    )

    # ── Build unified result dict ─────────────────────────────────────────
    return {
        # ── Phase 1 compatible fields ─────────────────────────────────────
        "expiry_date":        ocr_result["expiry_date"],
        "manufacturing_date": ocr_result["manufacturing_date"],
        "package_condition":  quality_result["package_condition"],
        "damage_percentage":  quality_result["damage_percentage"],
        "barcode":            barcode_result["number"],   # backward-compat key
        "quality_score":      quality_result["quality_score"],
        "status":             quality_result["status"],

        # ── Phase 2 extended fields ───────────────────────────────────────
        "barcode_number":     barcode_result["number"],
        "barcode_type":       barcode_result["type"],
        "batch_number":       ocr_result["batch_number"],
        "mrp":                ocr_result["mrp"],
        "net_weight":         ocr_result["net_weight"],
        "ocr_text":           ocr_result["ocr_text"],
        "ocr_confidence":     ocr_result["ocr_confidence"],
        "damage_type":        damage_result["damage_type"],
        "damage_conf":        str(round(damage_result["confidence"] * 100, 1)),
        "annotated_image":    damage_result["annotated_image"],
        "recommendation":     quality_result["recommendation"],
    }


# ── Safety wrapper ────────────────────────────────────────────────────────────

def _safe_call(fn, arg, default: dict) -> dict:
    """Call fn(arg) and return default dict on any exception."""
    try:
        return fn(arg)
    except Exception as e:
        print(f"[Analyzer] {fn.__name__} failed: {e}")
        return default
