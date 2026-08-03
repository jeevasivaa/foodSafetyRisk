"""
config.py — Application configuration constants
All environment-specific settings live here.
"""
import os

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Flask secret key for session encryption
SECRET_KEY = "foodquality_ai_secret_key_phase1_2026"

# SQLite database path
DB_PATH = os.path.join(BASE_DIR, "database", "foodquality.db")

# Upload folder
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

# Allowed image extensions
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

# Max upload size: 16 MB
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# Items per page for pagination
PER_PAGE = 8

# Admin seed credentials (used on first run if no admin exists)
ADMIN_NAME  = "System Admin"
ADMIN_EMAIL = "admin@foodquality.ai"
ADMIN_PASS  = "Admin@1234"
