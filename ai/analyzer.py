"""
ai/analyzer.py — Main AI pipeline entry point.
----------------------------------------------
Phase 3: Gemini API Vision Analysis.

Flask routes call ONLY this function:
    result = analyze_product(image_path)
"""
from ai.gemini_scanner import analyze_with_gemini

def analyze_product(image_path: str) -> dict:
    """
    Full AI analysis pipeline using Gemini 1.5.
    Replaces all local models (OCR, Barcode, YOLO).
    """
    return analyze_with_gemini(image_path)


# ── Safety wrapper ────────────────────────────────────────────────────────────

def _safe_call(fn, arg, default: dict) -> dict:
    """Call fn(arg) and return default dict on any exception."""
    try:
        return fn(arg)
    except Exception as e:
        print(f"[Analyzer] {fn.__name__} failed: {e}")
        return default
