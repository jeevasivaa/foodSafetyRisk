"""
routes/customer.py — Customer Blueprint
-----------------------------------------
Handles all customer-facing routes:
  /dashboard, /upload, /scan/*, /complaint/*, /profile
"""
import os
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from models.db import get_db
from ai.analyzer import analyze_product
from utils.helpers import (
    login_required, allowed_file, save_upload,
    paginate, generate_complaint_id
)
import config

customer = Blueprint("customer", __name__)


# ─── Dashboard ───────────────────────────────────────────────────────────────
@customer.route("/dashboard")
@login_required
def dashboard():
    """Customer dashboard with stats overview."""
    db      = get_db()
    user_id = session["user_id"]

    # Statistics
    total_scans = db.execute(
        """SELECT COUNT(*) as cnt FROM scans s
           JOIN products p ON s.product_id = p.id
           WHERE p.user_id = ?""",
        (user_id,)
    ).fetchone()["cnt"]

    total_complaints = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE user_id = ?",
        (user_id,)
    ).fetchone()["cnt"]

    pending_complaints = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE user_id = ? AND status = 'Pending'",
        (user_id,)
    ).fetchone()["cnt"]

    resolved_complaints = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE user_id = ? AND status = 'Resolved'",
        (user_id,)
    ).fetchone()["cnt"]

    # Recent scans (last 5)
    recent_scans = db.execute(
        """SELECT s.id, p.product_name, p.brand, s.status, s.quality_score, s.scan_date
           FROM scans s
           JOIN products p ON s.product_id = p.id
           WHERE p.user_id = ?
           ORDER BY s.scan_date DESC LIMIT 5""",
        (user_id,)
    ).fetchall()

    return render_template(
        "dashboard.html",
        total_scans=total_scans,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        resolved_complaints=resolved_complaints,
        recent_scans=recent_scans,
    )


# ─── Upload Product ───────────────────────────────────────────────────────────
@customer.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload a product image for analysis."""
    if request.method == "POST":
        product_name  = request.form.get("product_name", "").strip()
        brand         = request.form.get("brand", "").strip()
        category      = request.form.get("category", "").strip()
        purchase_date = request.form.get("purchase_date", "").strip()
        product_image = request.files.get("product_image")
        bill_image    = request.files.get("bill_image")

        # Validation
        errors = []
        if not product_name:
            errors.append("Product name is required.")
        if not brand:
            errors.append("Brand is required.")
        if not category:
            errors.append("Category is required.")
        if not purchase_date:
            errors.append("Purchase date is required.")
        if not product_image or product_image.filename == "":
            errors.append("Product image is required.")
        elif not allowed_file(product_image.filename):
            errors.append("Only JPG, JPEG, PNG files are allowed.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("upload.html", form=request.form)

        # Save product image (required)
        img_filename = save_upload(product_image, "products")
        if not img_filename:
            flash("Failed to save product image.", "danger")
            return render_template("upload.html", form=request.form)

        # Save bill image (optional)
        bill_filename = None
        if bill_image and bill_image.filename:
            if not allowed_file(bill_image.filename):
                flash("Bill image: only JPG, JPEG, PNG allowed.", "danger")
                return render_template("upload.html", form=request.form)
            bill_filename = save_upload(bill_image, "bills")

        db = get_db()
        cursor = db.execute(
            """INSERT INTO products (user_id, product_name, brand, category,
                                    purchase_date, image, bill_image)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session["user_id"], product_name, brand, category,
                purchase_date, img_filename, bill_filename,
            ),
        )
        db.commit()
        product_id = cursor.lastrowid

        flash("Product uploaded successfully! Running analysis...", "success")
        return redirect(url_for("customer.scan", product_id=product_id))

    return render_template("upload.html", form={})


# ─── Run Scan ─────────────────────────────────────────────────────────────────
@customer.route("/scan/<int:product_id>")
@login_required
def scan(product_id):
    """
    Run AI analysis on the uploaded product image.
    Calls analyze_product() — swap this in Phase 2 for real AI.
    """
    db      = get_db()
    user_id = session["user_id"]

    product = db.execute(
        "SELECT * FROM products WHERE id = ? AND user_id = ?",
        (product_id, user_id)
    ).fetchone()

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("customer.scan_history"))

    # Build full image path for AI module
    image_path = os.path.join(
        current_app.root_path, "static", "uploads", product["image"]
    )

    # ── AI Analysis (placeholder — swap in Phase 2) ───────────────────────
    result = analyze_product(image_path)
    # ─────────────────────────────────────────────────────────────────────

    # Store scan result in database
    cursor = db.execute(
        """INSERT INTO scans
           (product_id, expiry_date, manufacturing_date, package_condition,
            damage_percentage, barcode, quality_score, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            product_id,
            result["expiry_date"],
            result["manufacturing_date"],
            result["package_condition"],
            result["damage_percentage"],
            result["barcode"],
            result["quality_score"],
            result["status"],
        ),
    )
    db.commit()
    scan_id = cursor.lastrowid

    return redirect(url_for("customer.scan_result", scan_id=scan_id))


# ─── Scan Result ──────────────────────────────────────────────────────────────
@customer.route("/scan/result/<int:scan_id>")
@login_required
def scan_result(scan_id):
    """Display AI analysis result for a scan."""
    db      = get_db()
    user_id = session["user_id"]

    scan_data = db.execute(
        """SELECT s.*, p.product_name, p.brand, p.category,
                  p.purchase_date, p.image, p.bill_image, p.user_id
           FROM scans s
           JOIN products p ON s.product_id = p.id
           WHERE s.id = ? AND p.user_id = ?""",
        (scan_id, user_id)
    ).fetchone()

    if not scan_data:
        flash("Scan result not found.", "danger")
        return redirect(url_for("customer.scan_history"))

    # Check if complaint already raised for this scan
    complaint = db.execute(
        "SELECT id FROM complaints WHERE scan_id = ? AND user_id = ?",
        (scan_id, user_id)
    ).fetchone()

    return render_template(
        "scan_result.html",
        scan=scan_data,
        complaint=complaint,
    )


# ─── Scan History ─────────────────────────────────────────────────────────────
@customer.route("/scan/history")
@login_required
def scan_history():
    """Paginated scan history with search."""
    db      = get_db()
    user_id = session["user_id"]
    page    = request.args.get("page", 1, type=int)
    query   = request.args.get("q", "").strip()

    # Base query
    sql = """SELECT s.id, p.product_name, p.brand, p.category,
                    s.status, s.quality_score, s.scan_date, s.package_condition
             FROM scans s
             JOIN products p ON s.product_id = p.id
             WHERE p.user_id = ?"""
    params = [user_id]

    if query:
        sql += " AND (p.product_name LIKE ? OR p.brand LIKE ? OR s.status LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    sql += " ORDER BY s.scan_date DESC"

    all_scans = db.execute(sql, params).fetchall()
    # Convert to list of dicts for paginate helper
    all_scans = [dict(row) for row in all_scans]
    paged     = paginate(all_scans, page)

    return render_template(
        "scan_history.html",
        scans=paged["items"],
        pagination=paged,
        query=query,
    )


# ─── Delete Scan ──────────────────────────────────────────────────────────────
@customer.route("/scan/delete/<int:scan_id>", methods=["POST"])
@login_required
def delete_scan(scan_id):
    """Delete a scan (customer can only delete their own scans)."""
    db      = get_db()
    user_id = session["user_id"]

    scan_row = db.execute(
        """SELECT s.id FROM scans s
           JOIN products p ON s.product_id = p.id
           WHERE s.id = ? AND p.user_id = ?""",
        (scan_id, user_id)
    ).fetchone()

    if not scan_row:
        flash("Scan not found.", "danger")
        return redirect(url_for("customer.scan_history"))

    db.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    db.commit()
    flash("Scan deleted successfully.", "success")
    return redirect(url_for("customer.scan_history"))


# ─── Raise Complaint ──────────────────────────────────────────────────────────
@customer.route("/complaint/raise/<int:scan_id>", methods=["GET", "POST"])
@login_required
def raise_complaint(scan_id):
    """Complaint form — pre-filled from scan/product data."""
    db      = get_db()
    user_id = session["user_id"]

    scan_data = db.execute(
        """SELECT s.*, p.product_name, p.brand, p.category, p.bill_image
           FROM scans s
           JOIN products p ON s.product_id = p.id
           WHERE s.id = ? AND p.user_id = ?""",
        (scan_id, user_id)
    ).fetchone()

    if not scan_data:
        flash("Scan not found.", "danger")
        return redirect(url_for("customer.scan_history"))

    # Prevent duplicate complaint
    existing = db.execute(
        "SELECT id FROM complaints WHERE scan_id = ? AND user_id = ?",
        (scan_id, user_id)
    ).fetchone()
    if existing:
        flash("You have already raised a complaint for this scan.", "warning")
        return redirect(url_for("customer.scan_result", scan_id=scan_id))

    if request.method == "POST":
        description   = request.form.get("description", "").strip()
        complaint_img = request.files.get("complaint_image")
        bill_img      = request.files.get("bill_image")

        if not description:
            flash("Problem description is required.", "danger")
            return render_template("complaint_form.html", scan=scan_data)

        # Save complaint image (optional)
        comp_filename = save_upload(complaint_img, "complaints") if complaint_img and complaint_img.filename else None
        bill_filename = scan_data["bill_image"]  # reuse product bill or upload new
        if bill_img and bill_img.filename:
            new_bill = save_upload(bill_img, "bills")
            if new_bill:
                bill_filename = new_bill

        complaint_id = generate_complaint_id(db)

        db.execute(
            """INSERT INTO complaints
               (complaint_id, scan_id, user_id, description, image, bill_image, status)
               VALUES (?, ?, ?, ?, ?, ?, 'Pending')""",
            (complaint_id, scan_id, user_id, description, comp_filename, bill_filename),
        )
        db.commit()

        flash(f"Complaint {complaint_id} raised successfully!", "success")
        return redirect(url_for("customer.my_complaints"))

    return render_template("complaint_form.html", scan=scan_data)


# ─── My Complaints ────────────────────────────────────────────────────────────
@customer.route("/complaints")
@login_required
def my_complaints():
    """List all complaints raised by the logged-in customer."""
    db      = get_db()
    user_id = session["user_id"]
    page    = request.args.get("page", 1, type=int)

    all_complaints = db.execute(
        """SELECT c.*, p.product_name, p.brand, p.category
           FROM complaints c
           JOIN scans s ON c.scan_id = s.id
           JOIN products p ON s.product_id = p.id
           WHERE c.user_id = ?
           ORDER BY c.created_at DESC""",
        (user_id,)
    ).fetchall()
    all_complaints = [dict(row) for row in all_complaints]
    paged = paginate(all_complaints, page)

    return render_template(
        "complaints.html",
        complaints=paged["items"],
        pagination=paged,
    )


# ─── Complaint Details ────────────────────────────────────────────────────────
@customer.route("/complaint/<int:complaint_pk>")
@login_required
def complaint_details(complaint_pk):
    """View full details of a single complaint."""
    db      = get_db()
    user_id = session["user_id"]

    complaint = db.execute(
        """SELECT c.*, p.product_name, p.brand, p.category,
                  p.purchase_date, p.image as product_image,
                  s.quality_score, s.status as scan_status,
                  s.package_condition, s.expiry_date, s.manufacturing_date
           FROM complaints c
           JOIN scans s ON c.scan_id = s.id
           JOIN products p ON s.product_id = p.id
           WHERE c.id = ? AND c.user_id = ?""",
        (complaint_pk, user_id)
    ).fetchone()

    if not complaint:
        flash("Complaint not found.", "danger")
        return redirect(url_for("customer.my_complaints"))

    return render_template("complaint_details.html", complaint=complaint)


# ─── Profile ──────────────────────────────────────────────────────────────────
@customer.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """View and edit customer profile."""
    db      = get_db()
    user_id = session["user_id"]
    user    = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if request.method == "POST":
        action = request.form.get("action")

        # ── Update profile info ───────────────────────────────────────────
        if action == "update_profile":
            name  = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()

            if not name:
                flash("Name is required.", "danger")
                return render_template("profile.html", user=user)

            # Profile picture upload
            pic_file   = request.files.get("profile_pic")
            pic_filename = user["profile_pic"]
            if pic_file and pic_file.filename:
                saved = save_upload(pic_file, "profiles")
                if saved:
                    pic_filename = saved
                else:
                    flash("Invalid profile picture format.", "danger")
                    return render_template("profile.html", user=user)

            db.execute(
                "UPDATE users SET name = ?, phone = ?, profile_pic = ? WHERE id = ?",
                (name, phone, pic_filename, user_id),
            )
            db.commit()
            session["name"] = name
            flash("Profile updated successfully!", "success")
            return redirect(url_for("customer.profile"))

        # ── Change password ───────────────────────────────────────────────
        elif action == "change_password":
            current_pw  = request.form.get("current_password", "")
            new_pw      = request.form.get("new_password", "")
            confirm_pw  = request.form.get("confirm_password", "")

            if not check_password_hash(user["password"], current_pw):
                flash("Current password is incorrect.", "danger")
                return render_template("profile.html", user=user)

            if len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return render_template("profile.html", user=user)

            if new_pw != confirm_pw:
                flash("New passwords do not match.", "danger")
                return render_template("profile.html", user=user)

            db.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(new_pw), user_id),
            )
            db.commit()
            flash("Password changed successfully!", "success")
            return redirect(url_for("customer.profile"))

    # Refresh user from DB for display
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return render_template("profile.html", user=user)
