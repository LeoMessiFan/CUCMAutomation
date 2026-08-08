from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# UTC-4 (EDT) — adjust to UTC-5 in winter (EST)
LOCAL_OFFSET = timedelta(hours=-4)


def _to_local(dt):
    """Convert UTC datetime to local time string."""
    if dt is None:
        return ""
    # Handle both naive and aware datetimes
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt + LOCAL_OFFSET
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


class User(UserMixin, db.Model):
    """Portal admin user."""
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default="admin")
    created_at    = db.Column(db.DateTime, nullable=False,
                              default=lambda: datetime.now(timezone.utc))
    last_login    = db.Column(db.DateTime, nullable=True)

    jobs = db.relationship("JobHistory", backref="admin_user", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class JobHistory(db.Model):
    """Record of every provisioning job (manual or CSV)."""
    __tablename__ = "job_history"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Input parameters
    mirror_dn      = db.Column(db.String(50),  nullable=False)
    new_dn         = db.Column(db.String(50),  nullable=False)
    user_id_input  = db.Column(db.String(80),  nullable=False)
    full_name      = db.Column(db.String(200), nullable=False)
    vm_enable      = db.Column(db.Boolean,     nullable=False, default=False)
    phone_mac      = db.Column(db.String(20),  nullable=False)
    phone_model    = db.Column(db.String(50),  nullable=False)
    jabber_model   = db.Column(db.String(10),  nullable=False)

    # Job metadata
    source          = db.Column(db.String(10),  nullable=False, default="manual")
    status          = db.Column(db.String(20),  nullable=False, default="running")
    current_step    = db.Column(db.Integer,     nullable=False, default=0)
    log_output      = db.Column(db.Text,        nullable=True)
    error_message   = db.Column(db.String(500), nullable=True)

    # Timing
    started_at       = db.Column(db.DateTime, nullable=False,
                                 default=lambda: datetime.now(timezone.utc))
    finished_at      = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Float,    nullable=True)

    def to_dict(self):
        return {
            "id":             self.id,
            "mirror_dn":      self.mirror_dn,
            "new_dn":         self.new_dn,
            "user_id_input":  self.user_id_input,
            "full_name":      self.full_name,
            "vm_enable":      self.vm_enable,
            "phone_mac":      self.phone_mac,
            "phone_model":    self.phone_model,
            "jabber_model":   self.jabber_model,
            "source":         self.source,
            "status":         self.status,
            "current_step":   self.current_step,
            "log_output":     self.log_output or "",
            "error_message":  self.error_message or "",
            "started_at":     _to_local(self.started_at),
            "finished_at":    _to_local(self.finished_at),
            "duration_seconds": self.duration_seconds,
            "admin_username": self.admin_user.username if self.admin_user else "",
        }

    def __repr__(self):
        return f"<JobHistory {self.id} {self.status}>"
