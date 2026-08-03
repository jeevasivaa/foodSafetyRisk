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
