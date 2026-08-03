"""
routes/auth.py — Authentication Blueprint
------------------------------------------
Handles: /register, /login, /logout
"""
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from models.db import get_db

auth = Blueprint("auth", __name__)


# ─── Root redirect ────────────────────────────────────────────────────────────
@auth.route("/")
def index():
    """Redirect root to login or appropriate dashboard if already logged in."""
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("customer.dashboard"))
    return redirect(url_for("auth.login"))


# ─── Register ─────────────────────────────────────────────────────────────────
@auth.route("/register", methods=["GET", "POST"])
def register():
    """Customer self-registration page."""
    # Already logged in — redirect away
    if "user_id" in session:
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        phone    = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        # ── Server-side validation ────────────────────────────────────────────
        errors = []
        if not name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", form=request.form)

        db = get_db()

        # Check duplicate email
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            flash("An account with this email already exists.", "danger")
            return render_template("register.html", form=request.form)

        # Insert new customer
        db.execute(
            """INSERT INTO users (name, email, phone, password, role)
               VALUES (?, ?, ?, ?, 'customer')""",
            (name, email, phone, generate_password_hash(password)),
        )
        db.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form={})


# ─── Login ────────────────────────────────────────────────────────────────────
@auth.route("/login", methods=["GET", "POST"])
def login():
    """Login page — redirects based on role after authentication."""
    if "user_id" in session:
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("login.html")

        db   = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        # Store user info in session
        session.clear()
        session["user_id"] = user["id"]
        session["name"]    = user["name"]
        session["email"]   = user["email"]
        session["role"]    = user["role"]

        flash(f"Welcome back, {user['name']}!", "success")

        # Role-based redirect
        if user["role"] == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("customer.dashboard"))

    return render_template("login.html")


# ─── Logout ───────────────────────────────────────────────────────────────────
@auth.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))
