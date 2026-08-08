"""
app.py
──────
Flask application entry point.
"""

import os
import sys
import click
import bcrypt
from flask import Flask
from flask_login import LoginManager
from sqlalchemy import inspect, text

from config import Config
from database.models import db, User


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access the portal."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.auth      import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.api       import api_bp
    from routes.admin     import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    return app


app = create_app()


def _ensure_schema_upgrades():
    """Apply tiny SQLite-safe schema upgrades for existing portal.db files."""
    inspector = inspect(db.engine)
    if "job_history" not in inspector.get_table_names():
        return []

    existing_columns = {col["name"] for col in inspector.get_columns("job_history")}
    applied = []

    if "ai_diagnosis" not in existing_columns:
        db.session.execute(text("ALTER TABLE job_history ADD COLUMN ai_diagnosis TEXT"))
        db.session.commit()
        applied.append("job_history.ai_diagnosis")

    return applied


@app.cli.command("init-db")
def init_db():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        applied = _ensure_schema_upgrades()
        click.echo("✓ Database tables created.")
        for item in applied:
            click.echo(f"✓ Added column: {item}")


@app.cli.command("upgrade-db")
def upgrade_db():
    """Apply schema upgrades to an existing database."""
    with app.app_context():
        db.create_all()
        applied = _ensure_schema_upgrades()
        if applied:
            for item in applied:
                click.echo(f"✓ Added column: {item}")
        else:
            click.echo("✓ Database schema already up to date.")


@app.cli.command("create-admin")
@click.option("--username", prompt="Admin username")
@click.option("--password", prompt="Password", hide_input=True, confirmation_prompt=True)
def create_admin(username, password):
    """Create an admin user account."""
    with app.app_context():
        db.create_all()
        existing = User.query.filter_by(username=username).first()
        if existing:
            click.echo(f"✗ User '{username}' already exists.")
            sys.exit(1)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(username=username, password_hash=hashed, role="admin")
        db.session.add(user)
        db.session.commit()
        click.echo(f"✓ Admin user '{username}' created successfully.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host=Config.HOST, port=Config.PORT, debug=False)
