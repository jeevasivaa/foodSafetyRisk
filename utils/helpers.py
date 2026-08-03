"""
utils/helpers.py — Shared utility functions and decorators
-----------------------------------------------------------
"""
import os
import uuid
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.utils import secure_filename
import config


# ─── Auth Decorators ────────────────────────────────────────────────────────

def login_required(f):
    """Redirect to login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Redirect to login if user is not an admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            flash("Access denied. Admin only.", "danger")
            return redirect(url_for("customer.dashboard"))
        return f(*args, **kwargs)
    return decorated


# ─── File Upload Helpers ─────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    """Check if the file extension is in the allowed set (jpg, jpeg, png)."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


def save_upload(file_obj, subfolder: str = "") -> str | None:
    """
    Securely save an uploaded file to static/uploads/[subfolder]/.

    Args:
        file_obj: Werkzeug FileStorage object from request.files.
        subfolder: Optional subdirectory within uploads/.

    Returns:
        Saved filename (relative to static/uploads/) or None on failure.
    """
    if not file_obj or file_obj.filename == "":
        return None
    if not allowed_file(file_obj.filename):
        return None

    ext = file_obj.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    save_dir = os.path.join(config.UPLOAD_FOLDER, subfolder)
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, unique_name)
    file_obj.save(save_path)

    # Return relative path from static/uploads/
    return os.path.join(subfolder, unique_name).replace("\\", "/") if subfolder else unique_name


# ─── Pagination Helper ───────────────────────────────────────────────────────

def paginate(items: list, page: int, per_page: int = config.PER_PAGE) -> dict:
    """
    Slice a list into a single page and return pagination metadata.

    Returns dict with:
        items       — current page items
        page        — current page number
        per_page    — items per page
        total       — total item count
        total_pages — total number of pages
        has_prev    — bool
        has_next    — bool
    """
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end   = start + per_page

    return {
        "items":       items[start:end],
        "page":        page,
        "per_page":    per_page,
        "total":       total,
        "total_pages": total_pages,
        "has_prev":    page > 1,
        "has_next":    page < total_pages,
    }


# ─── Complaint ID Generator ──────────────────────────────────────────────────

def generate_complaint_id(db) -> str:
    """
    Generate a unique complaint ID in the format CMP-YYYY-NNNN.
    Reads the current max complaint number from DB to ensure uniqueness.
    """
    from datetime import datetime
    year = datetime.now().strftime("%Y")

    # Count existing complaints this year
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE complaint_id LIKE ?",
        (f"CMP-{year}-%",)
    ).fetchone()

    count = (row["cnt"] if row else 0) + 1
    return f"CMP-{year}-{count:04d}"
