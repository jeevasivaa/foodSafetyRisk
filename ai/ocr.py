"""
ai/ocr.py — Text extraction using EasyOCR.

Reads all text from the product image, then uses regex patterns to extract:
  - Expiry date        (EXP / BEST BEFORE / USE BY / BB)
  - Manufacturing date (MFD / MFG / MANUFACTURED / DOM)
  - Batch number       (BATCH / LOT / B/N / BN)
  - MRP                (MRP / Rs. / ₹)
  - Net weight         (NET WT / g / kg / ml / L)

All failures are caught and returned as "Not Detected" — the app never crashes.
"""
import re
from ai.ai_config import OCR_LANGUAGES, OCR_MIN_CONFIDENCE
from ai.utils import parse_date, clean_ocr_text

# ── Lazy EasyOCR initialisation ───────────────────────────────────────────────
# Reader is expensive to load (~2 s) so we cache a single instance.
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        try:
            import easyocr
            _reader = easyocr.Reader(OCR_LANGUAGES, gpu=False, verbose=False)
        except Exception as e:
            print(f"[OCR] Failed to initialise EasyOCR: {e}")
            _reader = None
    return _reader


# ── Regex patterns ────────────────────────────────────────────────────────────

# Date sub-pattern: matches most common date formats printed on packages
_DATE_PAT = (
    r"(?:"
    r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}"   # DD/MM/YYYY or DD-MM-YY
    r"|\d{1,2}[\/\-\.]\d{4}"                      # MM/YYYY
    r"|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}"      # YYYY/MM/DD
    r"|[A-Za-z]{3,9}\s\d{4}"                      # Jan 2026
    r"|\d{1,2}\s[A-Za-z]{3,9}\s\d{2,4}"          # 12 Jan 2026
    r"|\d{4}"                                      # year only
    r")"
)

_EXP_PAT   = re.compile(
    r"(?:EXP(?:IRY)?(?:\s*DATE)?|BEST\s*BEFORE|USE\s*BY|BB|B\.B|EXPIRY)\s*[:\.\-]?\s*(" + _DATE_PAT + r")",
    re.IGNORECASE
)
_MFD_PAT   = re.compile(
    r"(?:MF[DG]|MANUF(?:ACTUR(?:ED|ING))?(?:\s*DATE)?|DOM|PKD)\s*[:\.\-]?\s*(" + _DATE_PAT + r")",
    re.IGNORECASE
)
_BATCH_PAT = re.compile(
    r"(?:BATCH\s*(?:NO|NUMBER|CODE)?|LOT\s*(?:NO|NUMBER)?|B[\/\.]?N)\s*[:\.\-]?\s*([A-Z0-9\-\/]{3,20})",
    re.IGNORECASE
)
_MRP_PAT   = re.compile(
    r"(?:MRP|M\.R\.P\.?)\s*[:\.\-]?\s*(?:Rs\.?|INR|₹)?\s*(\d+(?:[.,]\d{1,2})?)",
    re.IGNORECASE
)
_WEIGHT_PAT = re.compile(
    r"(?:NET\s*(?:WT|WEIGHT|CONT(?:ENTS)?))\s*[:\.\-]?\s*([\d.]+\s*(?:g|kg|ml|l|oz|lb)(?:s)?)",
    re.IGNORECASE
)


def run_ocr(image_path: str) -> dict:
    """
    Extract text and structured fields from a product image.

    Returns:
        dict with keys:
            expiry_date        (str)
            manufacturing_date (str)
            batch_number       (str)
            mrp                (str)
            net_weight         (str)
            ocr_text           (str)  — full concatenated text
            ocr_confidence     (str)  — average confidence as percentage string
    """
    _empty = {
        "expiry_date":        "Not Detected",
        "manufacturing_date": "Not Detected",
        "batch_number":       "Not Detected",
        "mrp":                "Not Detected",
        "net_weight":         "Not Detected",
        "ocr_text":           "",
        "ocr_confidence":     "0",
    }

    try:
        reader = _get_reader()
        if reader is None:
            return _empty

        # ── Fast image resize for OCR ─────────────────────────────────────
        # Large camera images (4K+) are extremely slow on CPU.
        # Downscale to a max dimension of 1024px before OCR.
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return _empty

        h, w = img.shape[:2]
        max_dim = 1024
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        results = reader.readtext(img, detail=1, paragraph=False)

        if not results:
            return _empty

        # ── Aggregate text and confidence ─────────────────────────────────
        lines = []
        confidences = []
        for (_, text, conf) in results:
            if conf >= OCR_MIN_CONFIDENCE:
                lines.append(text)
                confidences.append(conf)

        full_text = " ".join(lines)
        avg_conf  = (sum(confidences) / len(confidences) * 100) if confidences else 0
        full_text_clean = clean_ocr_text(full_text)

        # ── Field extraction ──────────────────────────────────────────────
        expiry_date        = _extract(full_text_clean, _EXP_PAT,    parse_date)
        manufacturing_date = _extract(full_text_clean, _MFD_PAT,    parse_date)
        batch_number       = _extract(full_text_clean, _BATCH_PAT,  lambda x: x.strip().upper())
        mrp                = _extract(full_text_clean, _MRP_PAT,    lambda x: f"Rs. {x.strip()}")
        net_weight         = _extract(full_text_clean, _WEIGHT_PAT, lambda x: x.strip())

        return {
            "expiry_date":        expiry_date,
            "manufacturing_date": manufacturing_date,
            "batch_number":       batch_number,
            "mrp":                mrp,
            "net_weight":         net_weight,
            "ocr_text":           full_text_clean,
            "ocr_confidence":     f"{avg_conf:.1f}",
        }

    except Exception as e:
        print(f"[OCR] Error: {e}")
        return _empty


# ── Internal helper ───────────────────────────────────────────────────────────

def _extract(text: str, pattern: re.Pattern, transform) -> str:
    """
    Search text for pattern, apply transform to first match group 1.
    Returns "Not Detected" if nothing found.
    """
    try:
        m = pattern.search(text)
        if m:
            raw = m.group(1).strip()
            if raw:
                return transform(raw)
    except Exception:
        pass
    return "Not Detected"
