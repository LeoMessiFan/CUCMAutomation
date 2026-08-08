"""
routes/auth.py
──────────────
Login and logout routes.
"""

import bcrypt
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from database.models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET"])
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            login_user(user)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            return redirect(url_for("dashboard.dashboard"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
