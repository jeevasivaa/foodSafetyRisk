"""
routes/customer.py — Customer Blueprint
-----------------------------------------
Handles all customer-facing routes:
  /dashboard, /upload, /scan/*, /complaint/*, /profile
"""
import os
import base64
import uuid
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session, current_app, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from models.db import get_db
from services.inspection_service import perform_unified_inspection
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
        manual_barcode = request.form.get("manual_barcode", "").strip()
        
        if not product_image or product_image.filename == "":
            if not manual_barcode:
                errors.append("Product image or manual barcode is required.")
        elif not allowed_file(product_image.filename):
            errors.append("Only JPG, JPEG, PNG files are allowed.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("upload.html", form=request.form)

        # Save product image (optional if barcode is present)
        img_filename = ""
        if product_image and product_image.filename:
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
        
        manufacturing_date = request.form.get("manufacturing_date", "").strip()
        expiry_date = request.form.get("expiry_date", "").strip()

        flash("Product uploaded successfully! Running analysis...", "success")
        return redirect(url_for("customer.scan", product_id=product_id, manual_barcode=manual_barcode, mfg_date=manufacturing_date, exp_date=expiry_date))

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

    # Build full image path for AI module, or empty if no image provided
    if product["image"]:
        image_path = os.path.join(
            current_app.root_path, "static", "uploads", product["image"]
        )
    else:
        image_path = ""
    
    manual_barcode = request.args.get("manual_barcode", "").strip()
    mfg_date = request.args.get("mfg_date", "").strip()
    exp_date = request.args.get("exp_date", "").strip()

    # ── AI Analysis (Phase 3 Unified Workflow) ───────────────────────
    result = perform_unified_inspection(image_path, manual_barcode=manual_barcode, mfg_date=mfg_date, exp_date=exp_date)
    # ─────────────────────────────────────────────────────────────────────
    
    ai = result.get("ai_analysis", {})
    barcode_data = result.get("barcode", {})

    # Store scan result in database (Phase 2 extended columns)
    cursor = db.execute(
        """INSERT INTO scans
           (product_id, expiry_date, manufacturing_date, package_condition,
            damage_percentage, barcode, quality_score, status, summary,
            barcode_number, barcode_type, batch_number, mrp, net_weight,
            ocr_text, ocr_confidence, damage_type, damage_conf,
            annotated_image, recommendation, scan_type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            product_id,
            ai.get("expiry_date", "Not Detected"),
            ai.get("manufacturing_date", "Not Detected"),
            ai.get("package_condition", "Fair"),
            ai.get("damage_percentage", "0%"),
            barcode_data.get("number", "Not Detected"),
            ai.get("quality_score", "50"),
            ai.get("status", "Warning"),
            ai.get("summary", ""),
            barcode_data.get("number", "Not Detected"),
            barcode_data.get("type", ""),
            ai.get("batch_number", "Not Detected"),
            ai.get("mrp", "Not Detected"),
            ai.get("net_weight", "Not Detected"),
            ai.get("ocr_text", ""),
            ai.get("ocr_confidence", "0"),
            ai.get("damage_type", "Package Appears Normal"),
            ai.get("damage_conf", "0"),
            ai.get("annotated_image", ""),
            ai.get("recommendation", ""),
            "product_scan"
        ),
    )
    scan_id = cursor.lastrowid
    
    # Store AI analysis specifics in the new Phase 3 table
    import json
    db.execute(
        """INSERT INTO ai_analysis
           (scan_id, expiry_date, manufacturing_date, batch_number, mrp,
            package_condition, visible_defects, condition_score, risk_level,
            recommendation, raw_response_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            scan_id,
            ai.get("expiry_date", "Not Detected"),
            ai.get("manufacturing_date", "Not Detected"),
            ai.get("batch_number", "Not Detected"),
            ai.get("mrp", "Not Detected"),
            ai.get("package_condition", "Fair"),
            ai.get("damage_type", "Package Appears Normal"),
            ai.get("quality_score", "50"),
            ai.get("status", "Warning"),
            ai.get("recommendation", ""),
            json.dumps(ai)
        )
    )
    
    db.commit()

    return redirect(url_for("customer.scan_result", scan_id=scan_id))


# ── Camera Scan (AJAX) ─────────────────────────────────────────────────────────
@customer.route("/scan/camera", methods=["POST"])
@login_required
def camera_scan():
    """
    Accept a base64-encoded JPEG captured by the browser camera.
    Run the full AI pipeline and return JSON with the redirect URL.
    """
    try:
        data = request.get_json(silent=True) or {}
        image_b64 = data.get("image", "")

        if not image_b64:
            return jsonify({"error": "No image data received."}), 400

        # Strip data-URL prefix if present (e.g. "data:image/jpeg;base64,")
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            return jsonify({"error": "Invalid base64 image data."}), 400

        # Save to static/uploads/products/
        filename   = f"{uuid.uuid4().hex}.jpg"
        upload_dir = os.path.join(current_app.root_path, "static", "uploads", "products")
        os.makedirs(upload_dir, exist_ok=True)
        filepath   = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # Metadata
        product_name  = data.get("product_name", "Camera Capture").strip() or "Camera Capture"
        brand         = data.get("brand", "Unknown").strip()  or "Unknown"
        category      = data.get("category", "Other").strip() or "Other"
        purchase_date = data.get("purchase_date", "")
        if not purchase_date:
            from datetime import date as _date
            purchase_date = _date.today().isoformat()

        db = get_db()
        cursor = db.execute(
            """INSERT INTO products (user_id, product_name, brand, category,
                                    purchase_date, image)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session["user_id"], product_name, brand, category,
             purchase_date, f"products/{filename}"),
        )
        db.commit()
        product_id = cursor.lastrowid
        
        manual_barcode = data.get("manual_barcode", "").strip()
        mfg_date = data.get("mfg_date", "").strip()
        exp_date = data.get("exp_date", "").strip()

        # Run AI pipeline (Phase 3 Unified Workflow)
        result = perform_unified_inspection(filepath, manual_barcode=manual_barcode, mfg_date=mfg_date, exp_date=exp_date)
        
        ai = result.get("ai_analysis", {})
        barcode_data = result.get("barcode", {})

        cursor = db.execute(
            """INSERT INTO scans
               (product_id, expiry_date, manufacturing_date, package_condition,
                damage_percentage, barcode, quality_score, status, summary,
                barcode_number, barcode_type, batch_number, mrp, net_weight,
                ocr_text, ocr_confidence, damage_type, damage_conf,
                annotated_image, recommendation, scan_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                product_id,
                ai.get("expiry_date", "Not Detected"),
                ai.get("manufacturing_date", "Not Detected"),
                ai.get("package_condition", "Fair"),
                ai.get("damage_percentage", "0%"),
                barcode_data.get("number", "Not Detected"),
                ai.get("quality_score", "50"),
                ai.get("status", "Warning"),
                ai.get("summary", ""),
                barcode_data.get("number", "Not Detected"),
                barcode_data.get("type", ""),
                ai.get("batch_number", "Not Detected"),
                ai.get("mrp", "Not Detected"),
                ai.get("net_weight", "Not Detected"),
                ai.get("ocr_text", ""),
                ai.get("ocr_confidence", "0"),
                ai.get("damage_type", "Package Appears Normal"),
                ai.get("damage_conf", "0"),
                ai.get("annotated_image", ""),
                ai.get("recommendation", ""),
                "camera_scan"
            ),
        )
        scan_id = cursor.lastrowid
        
        # Store AI analysis specifics in the new Phase 3 table
        import json
        db.execute(
            """INSERT INTO ai_analysis
               (scan_id, expiry_date, manufacturing_date, batch_number, mrp,
                package_condition, visible_defects, condition_score, risk_level,
                recommendation, raw_response_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scan_id,
                ai.get("expiry_date", "Not Detected"),
                ai.get("manufacturing_date", "Not Detected"),
                ai.get("batch_number", "Not Detected"),
                ai.get("mrp", "Not Detected"),
                ai.get("package_condition", "Fair"),
                ai.get("damage_type", "Package Appears Normal"),
                ai.get("quality_score", "50"),
                ai.get("status", "Warning"),
                ai.get("recommendation", ""),
                json.dumps(ai)
            )
        )
        db.commit()

        return jsonify({
            "success":      True,
            "redirect_url": url_for("customer.scan_result", scan_id=scan_id),
        })

    except Exception as e:
        print(f"[Camera Scan] Error: {e}")
        return jsonify({"error": "Analysis failed. Please try again."}), 500


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
        
    scan_dict = dict(scan_data)
    
    # Fetch Open Food Facts data if available
    if scan_dict.get("barcode") and scan_dict["barcode"] != "Not Detected":
        off_data = db.execute("SELECT * FROM cached_products WHERE barcode = ?", (scan_dict["barcode"],)).fetchone()
        if off_data:
            scan_dict["off_data"] = dict(off_data)
            # Try to parse nutrition JSON
            try:
                import json
                if scan_dict["off_data"].get("nutrition_json"):
                    scan_dict["off_data"]["nutrition"] = json.loads(scan_dict["off_data"]["nutrition_json"])
            except:
                pass

    # Check if complaint already raised for this scan
    complaint = db.execute(
        "SELECT id FROM complaints WHERE scan_id = ? AND user_id = ?",
        (scan_id, user_id)
    ).fetchone()

    return render_template(
        "scan_result.html",
        scan=scan_dict,
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
        
        # Fetch user details for email
        user_info = db.execute("SELECT email, name FROM users WHERE id = ?", (user_id,)).fetchone()
        
        # Send emails
        from services.mail_service import send_complaint_acknowledgement, send_admin_notification
        
        complaint_title = f"{scan_data['product_name']} ({complaint_id})"
        if user_info:
            send_complaint_acknowledgement(user_info["email"], user_info["name"], complaint_title)
            send_admin_notification(complaint_title, user_info["name"])

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


# ─── Barcode API ──────────────────────────────────────────────────────────────
@customer.route("/api/product/barcode/<barcode>", methods=["GET"])
@login_required
def api_product_barcode(barcode):
    """
    Look up product information by barcode.
    Checks the local SQLite cache first; if not found, queries Open Food Facts.
    """
    from services.product_service import get_product_by_barcode
    
    barcode = barcode.strip()
    if not barcode:
        return jsonify({"success": False, "message": "Barcode is required"}), 400
        
    result = get_product_by_barcode(barcode)
    return jsonify(result)

@customer.route("/api/extract_barcode", methods=["POST"])
@login_required
def api_extract_barcode():
    """Extract barcode from an uploaded image file."""
    if "image" not in request.files:
        return jsonify({"success": False, "message": "No image provided"}), 400
        
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        import tempfile
        from services.barcode_service import detect_barcode
        
        fd, path = tempfile.mkstemp(suffix=".jpg")
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(file.read())
            
            barcode_data = detect_barcode(path)
            if barcode_data["detected"]:
                return jsonify({"success": True, "barcode": barcode_data["barcode"]})
            else:
                return jsonify({"success": False, "message": "No barcode detected in image"})
        finally:
            os.remove(path)
            
    return jsonify({"success": False, "message": "Invalid file type"}), 400
