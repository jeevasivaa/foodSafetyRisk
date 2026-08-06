"""
ai/quality_score.py — Compute overall quality score and recommendation.

Scoring table (deductions applied to base of 100):
  Expired product              : −60
  Expires in < 7 days          : −30
  Expires in 7–30 days         : −10
  Leakage detected             : −80
  Swollen Package              : −40
  Torn Package                 : −30
  Broken Seal                  : −20
  Damaged Label                : −10
  OCR fields not detected      : −5
  Barcode not detected         : −2

Score is clamped to [0, 100].
"""
from ai.utils import is_expired, days_until_expiry


# ── Damage deduction map ──────────────────────────────────────────────────────
_DAMAGE_DEDUCTIONS = {
    "Leakage":         80,
    "Swollen Package": 40,
    "Torn Package":    30,
    "Broken Seal":     20,
    "Damaged Label":   10,
}


def calculate_quality_score(ocr_result: dict, damage_result: dict) -> dict:
    """
    Compute quality score, status, package condition, and recommendation.

    Args:
        ocr_result:    Output dict from ai.ocr.run_ocr()
        damage_result: Output dict from ai.damage_detection.detect_damage()

    Returns:
        dict with keys:
            quality_score    (str)  e.g. "82"
            status           (str)  "Safe" | "Warning" | "Unsafe"
            package_condition(str)  "Good" | "Fair" | "Poor"
            recommendation   (str)  Human-readable advice
            damage_percentage(str)  e.g. "0%" or "30%"
    """
    score = 100
    reasons = []

    expiry_date = ocr_result.get("expiry_date", "Not Detected")
    days        = days_until_expiry(expiry_date)
    expired     = is_expired(expiry_date)

    # ── Date-based deductions ─────────────────────────────────────────────
    if expiry_date == "Not Detected":
        pass  # no penalty for unreadable date — not the product's fault
    elif expired:
        score -= 60
        reasons.append("Product is expired")
    elif days < 7:
        score -= 30
        reasons.append(f"Expires in {days} day(s)")
    elif days < 30:
        score -= 10
        reasons.append(f"Expires in {days} day(s)")

    # ── Damage-based deductions ───────────────────────────────────────────
    damage_type      = damage_result.get("damage_type", "Package Appears Normal")
    damage_detected  = damage_result.get("damage_detected", False)
    damage_conf      = damage_result.get("confidence", 0.0)
    damage_pct       = 0

    if damage_detected:
        for label, deduction in _DAMAGE_DEDUCTIONS.items():
            if label.lower() in damage_type.lower():
                # Scale deduction by confidence so uncertain detections are softer
                actual_deduction = int(deduction * max(damage_conf, 0.5))
                score -= actual_deduction
                damage_pct = actual_deduction
                reasons.append(f"{damage_type} detected")
                break

    # ── OCR quality deductions ────────────────────────────────────────────
    ocr_text = ocr_result.get("ocr_text", "")
    if not ocr_text.strip():
        score -= 5
        reasons.append("OCR failed to extract text")

    barcode_number = ocr_result.get("barcode_number", "Not Detected") \
        if "barcode_number" in ocr_result else "Not Detected"

    # ── Clamp ─────────────────────────────────────────────────────────────
    score = max(0, min(100, score))

    # ── Determine status ──────────────────────────────────────────────────
    if score >= 80:
        status            = "Safe"
        package_condition = "Good"
        recommendation    = _recommend_safe(days, expiry_date)
    elif score >= 50:
        status            = "Warning"
        package_condition = "Fair"
        recommendation    = _recommend_warning(reasons, days, expiry_date)
    else:
        status            = "Unsafe"
        package_condition = "Poor"
        recommendation    = _recommend_unsafe(reasons)

    return {
        "quality_score":     str(score),
        "status":            status,
        "package_condition": package_condition,
        "recommendation":    recommendation,
        "damage_percentage": f"{damage_pct}%",
    }


# ── Recommendation helpers ────────────────────────────────────────────────────

def _recommend_safe(days_left: int, expiry_date: str) -> str:
    if expiry_date == "Not Detected":
        return ("Product packaging appears in good condition. "
                "Verify expiry date manually before consuming.")
    if days_left < 30:
        return (f"Product is safe but expires soon ({days_left} days). "
                "Consume promptly.")
    return ("Product is safe to consume. Package is in good condition "
            "with no significant damage detected.")


def _recommend_warning(reasons: list, days_left: int, expiry_date: str) -> str:
    parts = ["Minor issues detected."]
    if expiry_date != "Not Detected" and days_left < 30:
        parts.append(f"Product expires in {days_left} day(s) — consume soon.")
    if reasons:
        parts.append("Check the product carefully before consuming.")
    parts.append("Consider raising a complaint if concerned.")
    return " ".join(parts)


def _recommend_unsafe(reasons: list) -> str:
    parts = ["DO NOT consume this product."]
    if reasons:
        parts.append(f"Issues: {', '.join(reasons)}.")
    parts.append("Please raise a complaint immediately.")
    return " ".join(parts)
