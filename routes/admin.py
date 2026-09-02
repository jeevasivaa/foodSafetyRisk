"""
routes/admin.py — Admin Blueprint
-----------------------------------
Handles all admin-facing routes:
  /admin/dashboard, /admin/users, /admin/scans, /admin/complaints
"""
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from models.db import get_db
from utils.helpers import admin_required, paginate

admin = Blueprint("admin", __name__, url_prefix="/admin")


# ─── Admin Dashboard ──────────────────────────────────────────────────────────
@admin.route("/dashboard")
@admin_required
def dashboard():
    """Admin overview: platform-wide stats and recent activity."""
    db = get_db()

    total_users = db.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE role = 'customer'"
    ).fetchone()["cnt"]

    total_scans = db.execute(
        "SELECT COUNT(*) as cnt FROM scans"
    ).fetchone()["cnt"]

    total_complaints = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints"
    ).fetchone()["cnt"]

    pending_complaints = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE status = 'Pending'"
    ).fetchone()["cnt"]

    resolved_complaints = db.execute(
        "SELECT COUNT(*) as cnt FROM complaints WHERE status = 'Resolved'"
    ).fetchone()["cnt"]

    # Recent scans (last 6)
    recent_scans = db.execute(
        """SELECT s.id, p.product_name, p.brand, u.name as customer,
                  s.status, s.quality_score, s.scan_date
           FROM scans s
           JOIN products p ON s.product_id = p.id
           JOIN users u ON p.user_id = u.id
           ORDER BY s.scan_date DESC LIMIT 6"""
    ).fetchall()

    # Recent complaints (last 6)
    recent_complaints = db.execute(
        """SELECT c.id, c.complaint_id, p.product_name, u.name as customer,
                  c.status, c.created_at
           FROM complaints c
           JOIN scans s ON c.scan_id = s.id
           JOIN products p ON s.product_id = p.id
           JOIN users u ON c.user_id = u.id
           ORDER BY c.created_at DESC LIMIT 6"""
    ).fetchall()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_scans=total_scans,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        resolved_complaints=resolved_complaints,
        recent_scans=recent_scans,
        recent_complaints=recent_complaints,
    )


# ─── All Users ────────────────────────────────────────────────────────────────
@admin.route("/users")
@admin_required
def users():
    """List all registered customers with search and pagination."""
    db    = get_db()
    page  = request.args.get("page", 1, type=int)
    query = request.args.get("q", "").strip()

    sql    = "SELECT * FROM users WHERE role = 'customer'"
    params = []
    if query:
        sql += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])
    sql += " ORDER BY created_at DESC"

    all_users = db.execute(sql, params).fetchall()
    all_users = [dict(row) for row in all_users]
    paged     = paginate(all_users, page)

    return render_template(
        "admin_users.html",
        users=paged["items"],
        pagination=paged,
        query=query,
    )


# ─── View User Profile ────────────────────────────────────────────────────────
@admin.route("/user/<int:user_id>")
@admin_required
def user_profile(user_id):
    """Admin view of a specific customer's profile."""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.users"))
        
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
    
    recent_scans = db.execute(
        """SELECT s.id, p.product_name, s.status, s.scan_date
           FROM scans s
           JOIN products p ON s.product_id = p.id
           WHERE p.user_id = ?
           ORDER BY s.scan_date DESC LIMIT 5""",
        (user_id,)
    ).fetchall()

    return render_template(
        "admin_user_profile.html",
        user=user,
        total_scans=total_scans,
        total_complaints=total_complaints,
        recent_scans=recent_scans
    )


# ─── All Scans ────────────────────────────────────────────────────────────────
@admin.route("/scans")
@admin_required
def scans():
    """List all scans across all customers with search and pagination."""
    db    = get_db()
    page  = request.args.get("page", 1, type=int)
    query = request.args.get("q", "").strip()

    sql = """SELECT s.id, p.product_name, p.brand, u.name as customer,
                    s.status, s.quality_score, s.package_condition, s.scan_date
             FROM scans s
             JOIN products p ON s.product_id = p.id
             JOIN users u ON p.user_id = u.id"""
    params = []

    if query:
        sql += """ WHERE (p.product_name LIKE ? OR p.brand LIKE ?
                          OR u.name LIKE ? OR s.status LIKE ?)"""
        like = f"%{query}%"
        params.extend([like, like, like, like])

    sql += " ORDER BY s.scan_date DESC"

    all_scans = db.execute(sql, params).fetchall()
    all_scans = [dict(row) for row in all_scans]
    paged     = paginate(all_scans, page)

    return render_template(
        "admin_scans.html",
        scans=paged["items"],
        pagination=paged,
        query=query,
    )


# ─── Delete Scan (Admin) ──────────────────────────────────────────────────────
@admin.route("/scan/delete/<int:scan_id>", methods=["POST"])
@admin_required
def delete_scan(scan_id):
    """Admin: permanently delete a scan record."""
    db = get_db()
    db.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    db.commit()
    flash("Scan deleted.", "success")
    return redirect(url_for("admin.scans"))


# ─── All Complaints ───────────────────────────────────────────────────────────
@admin.route("/complaints")
@admin_required
def complaints():
    """List all complaints with search, filter by status, and pagination."""
    db     = get_db()
    page   = request.args.get("page", 1, type=int)
    query  = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    sql = """SELECT c.id, c.complaint_id, p.product_name, p.brand,
                    u.name as customer, c.status, c.created_at, c.description
             FROM complaints c
             JOIN scans s ON c.scan_id = s.id
             JOIN products p ON s.product_id = p.id
             JOIN users u ON c.user_id = u.id
             WHERE 1=1"""
    params = []

    if query:
        sql += " AND (c.complaint_id LIKE ? OR p.product_name LIKE ? OR u.name LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if status:
        sql += " AND c.status = ?"
        params.append(status)

    sql += " ORDER BY c.created_at DESC"

    all_complaints = db.execute(sql, params).fetchall()
    all_complaints = [dict(row) for row in all_complaints]
    paged          = paginate(all_complaints, page)

    return render_template(
        "admin_complaints.html",
        complaints=paged["items"],
        pagination=paged,
        query=query,
        current_status=status,
    )

# ─── Complaint Details ────────────────────────────────────────────────────────
@admin.route("/complaint/<int:complaint_pk>")
@admin_required
def complaint_details(complaint_pk):
    """View full details of a single complaint."""
    db = get_db()

    complaint = db.execute(
        """SELECT c.*, p.product_name, p.brand, p.category,
                  p.purchase_date, p.image as product_image,
                  u.name as customer_name, u.email as customer_email,
                  s.quality_score, s.status as scan_status,
                  s.package_condition, s.expiry_date, s.manufacturing_date
           FROM complaints c
           JOIN scans s ON c.scan_id = s.id
           JOIN products p ON s.product_id = p.id
           JOIN users u ON c.user_id = u.id
           WHERE c.id = ?""",
        (complaint_pk,)
    ).fetchone()

    if not complaint:
        flash("Complaint not found.", "danger")
        return redirect(url_for("admin.complaints"))

    return render_template("admin_complaint_details.html", complaint=complaint)

def _send_status_update_email(db, complaint_id_pk, new_status):
    """Helper to fetch complaint details and send an email update."""
    complaint = db.execute(
        """SELECT c.complaint_id, u.name, u.email, p.product_name 
           FROM complaints c
           JOIN users u ON c.user_id = u.id
           JOIN scans s ON c.scan_id = s.id
           JOIN products p ON s.product_id = p.id
           WHERE c.id = ?""",
        (complaint_id_pk,)
    ).fetchone()
    
    if complaint:
        from services.mail_service import send_complaint_status_update
        title = f"{complaint['product_name']} ({complaint['complaint_id']})"
        send_complaint_status_update(
            complaint['email'], 
            complaint['name'], 
            title, 
            new_status, 
            None # Admin response text not implemented in UI yet
        )


# ─── Approve Complaint ────────────────────────────────────────────────────────
@admin.route("/complaint/<int:complaint_id>/approve", methods=["POST"])
@admin_required
def approve_complaint(complaint_id):
    db = get_db()
    db.execute(
        "UPDATE complaints SET status = 'Approved' WHERE id = ?",
        (complaint_id,)
    )
    db.commit()
    _send_status_update_email(db, complaint_id, 'Approved')
    flash("Complaint approved.", "success")
    return redirect(url_for("admin.complaints"))


# ─── Reject Complaint ─────────────────────────────────────────────────────────
@admin.route("/complaint/<int:complaint_id>/reject", methods=["POST"])
@admin_required
def reject_complaint(complaint_id):
    db = get_db()
    db.execute(
        "UPDATE complaints SET status = 'Rejected' WHERE id = ?",
        (complaint_id,)
    )
    db.commit()
    _send_status_update_email(db, complaint_id, 'Rejected')
    flash("Complaint rejected.", "warning")
    return redirect(url_for("admin.complaints"))


# ─── Resolve Complaint ────────────────────────────────────────────────────────
@admin.route("/complaint/<int:complaint_id>/resolve", methods=["POST"])
@admin_required
def resolve_complaint(complaint_id):
    db = get_db()
    db.execute(
        "UPDATE complaints SET status = 'Resolved' WHERE id = ?",
        (complaint_id,)
    )
    db.commit()
    _send_status_update_email(db, complaint_id, 'Resolved')
    flash("Complaint marked as resolved.", "success")
    return redirect(url_for("admin.complaints"))


# ─── Delete Complaint ─────────────────────────────────────────────────────────
@admin.route("/complaint/<int:complaint_id>/delete", methods=["POST"])
@admin_required
def delete_complaint(complaint_id):
    db = get_db()
    db.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))
    db.commit()
    flash("Complaint deleted.", "success")
    return redirect(url_for("admin.complaints"))
