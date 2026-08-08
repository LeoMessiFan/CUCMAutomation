"""
routes/api.py

Field rules:
  Required : mirror_dn, user_id, full_name, jabber_model
  Optional : new_dn      (leave blank for new users with no existing DN)
             phone_mac   (leave blank for Jabber-only provisioning)
             phone_model (required only if phone_mac is provided)
"""

import io
import csv
import threading
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user

from database.models import db, JobHistory
from core.runner import run_provisioning_job

api_bp = Blueprint("api", __name__, url_prefix="/api")

ALLOWED_JABBER = {"CSF", "TCT", "BOT", "TAB"}
CSV_COLUMNS = [
    "mirror_dn", "user_id", "full_name", "vm_enable",
    "new_dn", "phone_mac", "phone_model", "jabber_model"
]


def _validate_form(data: dict) -> list[str]:
    errors = []

    # Required fields only
    for field in ["mirror_dn", "user_id", "full_name", "jabber_model"]:
        if not data.get(field, "").strip():
            errors.append(f"Field '{field}' is required.")

    # MAC format validation only if provided
    mac = data.get("phone_mac", "").replace(":", "").replace("-", "").strip()
    if mac and (len(mac) != 12 or not all(c in "0123456789ABCDEFabcdef" for c in mac)):
        errors.append("Phone MAC must be exactly 12 hexadecimal characters.")

    # If MAC provided, model is required
    if mac and not data.get("phone_model", "").strip():
        errors.append("Phone Model is required when Phone MAC is provided.")

    jm = data.get("jabber_model", "").upper().strip()
    if jm and jm not in ALLOWED_JABBER:
        errors.append(f"Jabber model must be one of: {', '.join(ALLOWED_JABBER)}.")

    vm = data.get("vm_enable", "").lower().strip()
    if vm not in ("yes", "no", "true", "false", "1", "0"):
        errors.append("Voicemail must be 'yes' or 'no'.")

    return errors


def _create_job(data: dict, source: str = "manual") -> JobHistory:
    vm_val = data.get("vm_enable", "no").lower().strip()
    vm_bool = vm_val in ("yes", "true", "1")

    job = JobHistory(
        user_id       = current_user.id,
        mirror_dn     = data["mirror_dn"].strip(),
        new_dn        = data.get("new_dn", "").strip(),
        user_id_input = data["user_id"].strip(),
        full_name     = data["full_name"].strip(),
        vm_enable     = vm_bool,
        phone_mac     = data.get("phone_mac", "").replace(":", "").replace("-", "").upper().strip(),
        phone_model   = data.get("phone_model", "").strip(),
        jabber_model  = data["jabber_model"].upper().strip(),
        source        = source,
        status        = "running",
        current_step  = 0,
        log_output    = "",
        started_at    = datetime.now(timezone.utc),
    )
    db.session.add(job)
    db.session.commit()
    return job


@api_bp.route("/run-job", methods=["POST"])
@login_required
def run_job():
    data = request.get_json(silent=True) or request.form.to_dict()
    errors = _validate_form(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400
    job = _create_job(data, source="manual")
    app = current_app._get_current_object()
    t = threading.Thread(target=run_provisioning_job, args=(job.id, app), daemon=True)
    t.start()
    return jsonify({"success": True, "job_id": job.id, "status": "running"})


@api_bp.route("/job-status/<int:job_id>", methods=["GET"])
@login_required
def job_status(job_id):
    job = db.session.get(JobHistory, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict())


@api_bp.route("/download-template", methods=["GET"])
@login_required
def download_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    writer.writerow(["19786007919", "jsmith", "John Smith", "yes", "", "", "", "CSF"])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="uc_provisioning_template.csv"
    )


@api_bp.route("/upload-csv", methods=["POST"])
@login_required
def upload_csv():
    if current_user.role != "admin":
        return jsonify({"success": False, "errors": ["CSV upload is restricted to admins."]}), 403
    if "csv_file" not in request.files:
        return jsonify({"success": False, "errors": ["No file uploaded."]}), 400
    file = request.files["csv_file"]
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "errors": ["File must be a .csv file."]}), 400

    content = file.read().decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(content))

    missing_cols = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
    if missing_cols:
        return jsonify({"success": False,
            "errors": [f"Missing columns: {', '.join(missing_cols)}."]}), 400

    job_ids, row_errors = [], []
    app = current_app._get_current_object()

    for i, row in enumerate(reader, start=2):
        row_data = {k: (v or "").strip() for k, v in row.items()}
        errors = _validate_form(row_data)
        if errors:
            row_errors.append({"row": i, "errors": errors})
            continue
        job = _create_job(row_data, source="csv")
        job_ids.append({"job_id": job.id, "row": i, "user": row_data.get("user_id")})
        t = threading.Thread(target=run_provisioning_job, args=(job.id, app), daemon=True)
        t.start()

    return jsonify({"success": True, "jobs_queued": len(job_ids),
                    "jobs": job_ids, "row_errors": row_errors})
