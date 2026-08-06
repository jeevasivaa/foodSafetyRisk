"""
ai/damage_detection.py — Package damage detection.

Strategy (two-tier):
  Tier 1 (preferred): YOLOv8 model loaded from ai/weights/best.pt
  Tier 2 (fallback):  OpenCV heuristic analysis when best.pt is absent

OpenCV heuristic checks:
  1. Edge density (Canny) — torn / rough edges
  2. HSV colour anomalies — stains, leakage (unusual hue clusters)
  3. Large irregular contours — bulging / swollen areas
  4. Label region uniformity — damaged / wrinkled label
"""
import os
import uuid
import cv2
import numpy as np

from ai.ai_config import (
    MODEL_PATH, DAMAGE_CONFIDENCE_THRESHOLD,
    DAMAGE_CLASSES, RESULTS_FOLDER
)
from ai.preprocessing import load_bgr
from ai.utils import unique_filename

# ── YOLO lazy loader ──────────────────────────────────────────────────────────
_yolo_model  = None
_yolo_tried  = False   # avoid re-trying after a failed load


def _get_yolo():
    global _yolo_model, _yolo_tried
    if _yolo_tried:
        return _yolo_model
    _yolo_tried = True
    if not os.path.exists(MODEL_PATH):
        print(f"[Damage] best.pt not found at {MODEL_PATH} — using heuristic fallback.")
        return None
    try:
        from ultralytics import YOLO
        _yolo_model = YOLO(MODEL_PATH)
        print("[Damage] YOLOv8 model loaded successfully.")
        return _yolo_model
    except Exception as e:
        print(f"[Damage] Failed to load YOLO: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def detect_damage(image_path: str) -> dict:
    """
    Detect package damage and produce an annotated image.

    Returns:
        dict with keys:
            damage_detected  (bool)
            damage_type      (str)   e.g. "Torn Package" / "Package Appears Normal"
            confidence       (float) 0–1
            annotated_image  (str)   filename relative to static/ (e.g. "results/abc.jpg")
                                     or "" if save fails
    """
    _safe = {
        "damage_detected": False,
        "damage_type":     "Package Appears Normal",
        "confidence":      0.0,
        "annotated_image": "",
    }

    try:
        img_bgr = load_bgr(image_path)
        if img_bgr is None:
            return _safe

        model = _get_yolo()

        if model is not None:
            result = _yolo_detect(model, img_bgr, image_path)
        else:
            result = _heuristic_detect(img_bgr)

        # Save annotated image
        annotated_filename = _save_annotated(result["annotated_bgr"])
        result.pop("annotated_bgr", None)
        result["annotated_image"] = annotated_filename

        return result

    except Exception as e:
        print(f"[Damage] Error: {e}")
        return _safe


# ── YOLO detection ────────────────────────────────────────────────────────────

def _yolo_detect(model, img_bgr: np.ndarray, image_path: str) -> dict:
    """Run YOLOv8 inference and draw bounding boxes."""
    try:
        results = model(image_path, conf=DAMAGE_CONFIDENCE_THRESHOLD, verbose=False)
        annotated = results[0].plot()  # BGR numpy with boxes drawn

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return {
                "damage_detected": False,
                "damage_type":     "Package Appears Normal",
                "confidence":      0.0,
                "annotated_bgr":   annotated,
            }

        # Pick highest-confidence detection
        confs  = boxes.conf.cpu().numpy()
        cls_ids = boxes.cls.cpu().numpy().astype(int)
        best_idx = int(np.argmax(confs))
        best_conf = float(confs[best_idx])
        cls_id   = cls_ids[best_idx]

        # Map class id → label
        damage_type = (DAMAGE_CLASSES[cls_id]
                       if cls_id < len(DAMAGE_CLASSES)
                       else f"Defect-{cls_id}")

        return {
            "damage_detected": True,
            "damage_type":     damage_type,
            "confidence":      round(best_conf, 3),
            "annotated_bgr":   annotated,
        }
    except Exception as e:
        print(f"[Damage] YOLO inference error: {e}")
        return _heuristic_detect(img_bgr)


# ── OpenCV Heuristic detection ────────────────────────────────────────────────

def _heuristic_detect(img_bgr: np.ndarray) -> dict:
    """
    Multi-signal heuristic damage detector using OpenCV.
    Returns same dict structure as _yolo_detect (with annotated_bgr).
    """
    annotated = img_bgr.copy()
    h, w = img_bgr.shape[:2]

    signals = []   # list of (damage_type, confidence, description)

    # ── Signal 1: Edge density (torn / rough package) ─────────────────────
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 200)
    edge_density = np.sum(edges > 0) / (h * w)
    if edge_density > 0.18:
        conf = min(0.55 + (edge_density - 0.18) * 2.5, 0.88)
        signals.append(("Torn Package", conf, f"edge_density={edge_density:.3f}"))

    # ── Signal 2: Colour anomalies (leakage / stains) ─────────────────────
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Dark brownish / yellowish blobs outside the normal product colour range
    mask_dark  = cv2.inRange(hsv, np.array([10, 40, 20]),  np.array([35, 255, 120]))
    mask_stain = cv2.inRange(hsv, np.array([0, 60, 30]),   np.array([15, 255, 150]))
    stain_ratio = (np.sum(mask_dark) + np.sum(mask_stain)) / (h * w * 255)
    if stain_ratio > 0.04:
        conf = min(0.50 + stain_ratio * 8, 0.85)
        signals.append(("Leakage", conf, f"stain_ratio={stain_ratio:.4f}"))
        # Draw stain highlight
        contours, _ = cv2.findContours(
            cv2.bitwise_or(mask_dark, mask_stain),
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            if cv2.contourArea(cnt) > 500:
                x, y, bw, bh = cv2.boundingRect(cnt)
                cv2.rectangle(annotated, (x, y), (x + bw, y + bh), (0, 0, 255), 2)

    # ── Signal 3: Large irregular contours (swollen / deformed) ──────────
    blur   = cv2.GaussianBlur(gray, (11, 11), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    large_blobs = [c for c in contours if cv2.contourArea(c) > 0.15 * h * w]
    if large_blobs:
        for cnt in large_blobs:
            hull   = cv2.convexHull(cnt)
            hull_a = cv2.contourArea(hull)
            cnt_a  = cv2.contourArea(cnt)
            if hull_a > 0:
                solidity = cnt_a / hull_a
                if solidity < 0.75:   # highly non-convex → swollen / irregular
                    conf = min(0.50 + (0.75 - solidity) * 2, 0.80)
                    signals.append(("Swollen Package", conf,
                                    f"solidity={solidity:.3f}"))
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    cv2.rectangle(annotated, (x, y), (x + bw, y + bh), (0, 165, 255), 2)

    # ── Signal 4: Low label uniformity (damaged / wrinkled label) ────────
    label_region = gray[int(h * 0.1): int(h * 0.9),
                        int(w * 0.1): int(w * 0.9)]
    std_dev = float(np.std(label_region))
    if std_dev > 72:
        conf = min(0.35 + (std_dev - 72) / 120, 0.65)
        signals.append(("Damaged Label", conf, f"label_std={std_dev:.1f}"))

    # ── Aggregate ──────────────────────────────────────────────────────────
    if not signals:
        return {
            "damage_detected": False,
            "damage_type":     "Package Appears Normal",
            "confidence":      0.0,
            "annotated_bgr":   annotated,
        }

    # Take the highest-confidence signal
    signals.sort(key=lambda x: x[1], reverse=True)
    best_type, best_conf, _ = signals[0]

    # Draw summary label on image
    label_text = f"{best_type} ({best_conf:.0%})"
    cv2.putText(annotated, label_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)

    return {
        "damage_detected": True,
        "damage_type":     best_type,
        "confidence":      round(best_conf, 3),
        "annotated_bgr":   annotated,
    }


# ── Save annotated image ──────────────────────────────────────────────────────

def _save_annotated(annotated_bgr: np.ndarray) -> str:
    """
    Save the annotated BGR image to static/results/.
    Returns filename relative to static/ (e.g. "results/abc.jpg") or "".
    """
    if annotated_bgr is None:
        return ""
    try:
        os.makedirs(RESULTS_FOLDER, exist_ok=True)
        filename = unique_filename("jpg")
        filepath = os.path.join(RESULTS_FOLDER, filename)
        cv2.imwrite(filepath, annotated_bgr)
        return f"results/{filename}"
    except Exception as e:
        print(f"[Damage] Failed to save annotated image: {e}")
        return ""
