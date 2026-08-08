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


@app.cli.command("init-db")
def init_db():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        click.echo("✓ Database tables created.")


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
