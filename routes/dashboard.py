"""
routes/dashboard.py
───────────────────
Main provisioning dashboard.
"""

from flask import Blueprint, render_template
from flask_login import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@dashboard_bp.route("/history")
@login_required
def history():
    from database.models import JobHistory
    jobs = JobHistory.query.order_by(JobHistory.started_at.desc()).all()
    return render_template("history.html", jobs=jobs)
