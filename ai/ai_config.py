"""
ai/ai_config.py — Central configuration for all Phase 2 AI modules.
All AI modules import settings from here.
"""
import os

# Base directory of the project (parent of ai/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ── YOLO / Damage Detection ──────────────────────────────────────────────────
# Path to trained YOLOv8 weights file.
# If the file does not exist, damage_detection.py automatically falls back
# to the OpenCV heuristic detector.
MODEL_PATH = os.path.join(BASE_DIR, "ai", "weights", "best.pt")

# Minimum YOLO confidence to count a detection as a real defect
DAMAGE_CONFIDENCE_THRESHOLD = 0.35

# Class names that the YOLO model can detect (must match training labels)
DAMAGE_CLASSES = [
    "Torn Package",
    "Broken Seal",
    "Leakage",
    "Swollen Package",
    "Damaged Label",
]

# ── OCR ───────────────────────────────────────────────────────────────────────
# Languages passed to easyocr.Reader — add more if needed, e.g. ['en', 'hi']
OCR_LANGUAGES = ["en"]

# Minimum OCR character-level confidence (0–1) to include a word
OCR_MIN_CONFIDENCE = 0.25

# ── Image Pre-processing ─────────────────────────────────────────────────────
# Resize the longest side of the image to this value before processing.
# Keeps aspect ratio. Larger = more accurate OCR; smaller = faster.
MAX_IMAGE_SIZE = 1280  # pixels

# ── Results Folder ────────────────────────────────────────────────────────────
# Annotated images (YOLO bounding boxes / heuristic overlays) are saved here.
# Path is relative to the Flask static folder.
RESULTS_FOLDER = os.path.join(BASE_DIR, "static", "results")

# Ensure the results directory exists at import time
os.makedirs(RESULTS_FOLDER, exist_ok=True)
