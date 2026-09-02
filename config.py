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

# Mail Settings
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

MAIL_SERVER   = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT     = int(os.getenv("MAIL_PORT", 587))
MAIL_USE_TLS  = os.getenv("MAIL_USE_TLS", "True") == "True"
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
