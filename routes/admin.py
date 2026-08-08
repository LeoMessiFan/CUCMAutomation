"""
routes/admin.py
───────────────
Admin-only user management routes.
Only users with role='admin' can access these pages.
"""

import bcrypt
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from database.models import db, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator: only allow users with role='admin'."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Access denied — admin only.", "error")
            return redirect(url_for("dashboard.dashboard"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin.html", users=all_users)


@admin_bp.route("/users/create", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role     = request.form.get("role", "user").strip()

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("admin.users"))

    if role not in ("admin", "user"):
        role = "user"

    existing = User.query.filter_by(username=username).first()
    if existing:
        flash(f"Username '{username}' already exists.", "error")
        return redirect(url_for("admin.users"))

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(
        username=username,
        password_hash=hashed,
        role=role,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(user)
    db.session.commit()
    flash(f"User '{username}' created successfully.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.users"))

    # Prevent deleting yourself
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))

    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.users"))

    new_password = request.form.get("new_password", "").strip()
    if not new_password:
        flash("New password cannot be empty.", "error")
        return redirect(url_for("admin.users"))

    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    user.password_hash = hashed
    db.session.commit()
    flash(f"Password for '{user.username}' reset successfully.", "success")
    return redirect(url_for("admin.users"))
