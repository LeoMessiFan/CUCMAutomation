"""
core/runner.py

Step logic:
  Step 1 — Always runs (get mirror device info)
  Step 2 — Skipped if new_dn is blank (new user with no existing DN)
  Step 3 — Skipped if phone_mac is blank (Jabber-only)
  Step 4 — Always runs (Jabber)
  Step 5 — Always runs (update end user)
"""

import os
os.environ["TZ"] = "America/New_York"
import time
time.tzset()
from datetime import datetime, timezone

from database.models import db, JobHistory
from core.automation import (
    get_mirror_devices,
    get_line_pt,
    get_line_config,
    get_phone_config,
    add_line_config,
    add_phone_config,
    add_jabber_config,
    update_user,
    update_user_pri_dn,
)

STEPS = [
    "Resolving Mirror Device",
    "Configuring New DN",
    "Provisioning Physical Phone",
    "Provisioning Jabber Client",
    "Updating End User",
]


def _append_log(job_id, app, message, step=None):
    with app.app_context():
        job = db.session.get(JobHistory, job_id)
        if job:
            ts = datetime.now().strftime("%H:%M:%S")
            job.log_output = (job.log_output or "") + f"[{ts}] {message}\n"
            if step is not None:
                job.current_step = step
            db.session.commit()


def _fail_job(job_id, app, error):
    with app.app_context():
        job = db.session.get(JobHistory, job_id)
        if job:
            ts = datetime.now().strftime("%H:%M:%S")
            job.log_output = (job.log_output or "") + f"[{ts}] ❌ ERROR: {error}\n"
            job.status = "failed"
            job.error_message = error[:500]
            job.finished_at = datetime.now(timezone.utc)
            if job.started_at:
                # Ensure both datetimes are naive UTC for subtraction
                started = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
                finished = job.finished_at.replace(tzinfo=None)
                job.duration_seconds = (finished - started).total_seconds()
            db.session.commit()


def _complete_job(job_id, app):
    with app.app_context():
        job = db.session.get(JobHistory, job_id)
        if job:
            ts = datetime.now().strftime("%H:%M:%S")
            job.log_output = (job.log_output or "") + f"[{ts}] ✅ All steps completed successfully.\n"
            job.status = "success"
            job.current_step = 5
            job.finished_at = datetime.now(timezone.utc)
            if job.started_at:
                # Ensure both datetimes are naive UTC for subtraction
                started = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
                finished = job.finished_at.replace(tzinfo=None)
                job.duration_seconds = (finished - started).total_seconds()
            db.session.commit()


def run_provisioning_job(job_id, app):
    with app.app_context():
        job = db.session.get(JobHistory, job_id)
        if not job:
            return
        params = {
            "mirror_dn":    job.mirror_dn,
            "new_dn":       job.new_dn or "",
            "user_id":      job.user_id_input,
            "full_name":    job.full_name,
            "vm_enable":    job.vm_enable,
            "phone_mac":    job.phone_mac.upper() if job.phone_mac else "",
            "phone_model":  job.phone_model or "",
            "jabber_model": job.jabber_model,
        }

    _append_log(job_id, app, f"🚀 Starting provisioning for {params['full_name']} ({params['user_id']})")
    _append_log(job_id, app, f"   Mirror DN : {params['mirror_dn']}")
    _append_log(job_id, app, f"   New DN    : {params['new_dn'] or '(not provided — Step 2 will be skipped)'}")
    _append_log(job_id, app, f"   Phone     : {'SEP' + params['phone_mac'] + ' (Model: ' + params['phone_model'] + ')' if params['phone_mac'] else '(not provided — Step 3 will be skipped)'}")
    _append_log(job_id, app, f"   Jabber    : {params['jabber_model'].upper()}{params['user_id']}")

    # ── STEP 1 — Always runs ─────────────────────────────────────────────────
    _append_log(job_id, app, "─" * 50)
    _append_log(job_id, app, f"[Step 1/5] {STEPS[0]}...", step=1)
    try:
        mirror_phone, mirror_j4w = get_mirror_devices(params["mirror_dn"])
        _append_log(job_id, app, f"   SEP Device : {mirror_phone or 'Not found'}")
        _append_log(job_id, app, f"   CSF Device : {mirror_j4w  or 'Not found'}")

        line_pt = get_line_pt(params["mirror_dn"])
        _append_log(job_id, app, f"   Partition  : {line_pt}")

        line_cfg = get_line_config(params["mirror_dn"])
        _append_log(job_id, app, f"   Line CSS   : {line_cfg['line_css']}")
        _append_log(job_id, app, f"   VM Profile : {line_cfg['vm_profile']}")
        _append_log(job_id, app, f"   Fwd CSS    : {line_cfg['line_fwdcss']}")

        # Try SEP first, fall back to CSF if no SEP device found
        mirror_device = mirror_phone or mirror_j4w
        phone_cfg = get_phone_config(mirror_device) if mirror_device else {}
        if phone_cfg:
            _append_log(job_id, app, f"   Config from: {mirror_device}")
            _append_log(job_id, app, f"   Device Pool: {phone_cfg.get('phone_dp')}")
        if not phone_cfg:
            raise RuntimeError("Could not retrieve device config from SEP or CSF device.")

        _append_log(job_id, app, "   ✔ Step 1 complete.")
    except Exception as e:
        _fail_job(job_id, app, f"Step 1 failed — {e}")
        return

    # ── STEP 2 — Skipped if new_dn is blank ──────────────────────────────────
    _append_log(job_id, app, "─" * 50)
    _append_log(job_id, app, f"[Step 2/5] {STEPS[1]}...", step=2)

    if params["new_dn"]:
        try:
            result = add_line_config(
                new_dn      = params["new_dn"],
                line_pt     = line_pt,
                full_name   = params["full_name"],
                vm_enable   = params["vm_enable"],
                line_css    = line_cfg["line_css"],
                vm_profile  = line_cfg["vm_profile"],
                line_fwdcss = line_cfg["line_fwdcss"],
            )
            _append_log(job_id, app, f"   DN '{params['new_dn']}' {result} successfully.")
            _append_log(job_id, app, "   ✔ Step 2 complete.")
        except Exception as e:
            _fail_job(job_id, app, f"Step 2 failed — {e}")
            return
    else:
        _append_log(job_id, app, "   ⏭ Skipped — no New DN provided (new user).")
        _append_log(job_id, app, "   ✔ Step 2 skipped.")

    # ── STEP 3 — Skipped if phone_mac is blank ───────────────────────────────
    _append_log(job_id, app, "─" * 50)
    _append_log(job_id, app, f"[Step 3/5] {STEPS[2]}...", step=3)

    if params["phone_mac"] and params["phone_model"]:
        try:
            result = add_phone_config(
                phone_mac      = params["phone_mac"],
                phone_model    = params["phone_model"],
                phone_protocol = phone_cfg.get("phone_protocol", "SIP"),
                phone_css      = phone_cfg.get("phone_css", ""),
                phone_dp       = phone_cfg.get("phone_dp", ""),
                phone_loc      = phone_cfg.get("phone_loc", ""),
                phone_mrgl     = phone_cfg.get("phone_mrgl", ""),
                full_name      = params["full_name"],
                user_id        = params["user_id"],
                new_dn         = params["new_dn"],
                line_pt        = line_pt,
                line_mask      = phone_cfg.get("line_mask", ""),
            )
            _append_log(job_id, app, f"   SEP{params['phone_mac']} {result} successfully.")
            _append_log(job_id, app, "   ✔ Step 3 complete.")
        except Exception as e:
            _fail_job(job_id, app, f"Step 3 failed — {e}")
            return
    else:
        _append_log(job_id, app, "   ⏭ Skipped — no Phone MAC provided.")
        _append_log(job_id, app, "   ✔ Step 3 skipped.")

    # ── STEP 4 — Always runs ─────────────────────────────────────────────────
    _append_log(job_id, app, "─" * 50)
    _append_log(job_id, app, f"[Step 4/5] {STEPS[3]}...", step=4)
    try:
        result = add_jabber_config(
            jabber_model = params["jabber_model"],
            user_id      = params["user_id"],
            full_name    = params["full_name"],
            phone_css    = phone_cfg.get("phone_css", ""),
            phone_dp     = phone_cfg.get("phone_dp", ""),
            phone_loc    = phone_cfg.get("phone_loc", ""),
            phone_mrgl   = phone_cfg.get("phone_mrgl", ""),
            new_dn       = params["new_dn"] or params["mirror_dn"],
            line_pt      = line_pt,
            line_mask    = phone_cfg.get("line_mask", ""),
        )
        jm = params["jabber_model"].upper()
        _append_log(job_id, app, f"   {jm}{params['user_id']} {result} successfully.")
        _append_log(job_id, app, "   ✔ Step 4 complete.")
    except Exception as e:
        _fail_job(job_id, app, f"Step 4 failed — {e}")
        return

    # ── STEP 5 — Always runs ─────────────────────────────────────────────────
    _append_log(job_id, app, "─" * 50)
    _append_log(job_id, app, f"[Step 5/5] {STEPS[4]}...", step=5)
    try:
        update_user(params["user_id"], params["jabber_model"])
        _append_log(job_id, app, f"   End user '{params['user_id']}' updated.")

        # Use User DN if provided, otherwise skip setting primary DN
        primary_dn = params["new_dn"] if params["new_dn"] else None
        if primary_dn:
            update_user_pri_dn(params["user_id"], primary_dn, line_pt)
            _append_log(job_id, app, f"   Primary DN set to {primary_dn}.")
        else:
            _append_log(job_id, app, "   ⏭ Primary DN not set — no User DN provided.")
        _append_log(job_id, app, "   ✔ Step 5 complete.")
    except Exception as e:
        _fail_job(job_id, app, f"Step 5 failed — {e}")
        return

    _complete_job(job_id, app)
