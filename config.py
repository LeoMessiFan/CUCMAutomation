import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Flask ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        os.path.dirname(__file__), "database", "portal.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── AXL / CUCM ─────────────────────────────────────────
    AXL_USERNAME = os.environ.get("AXL_USERNAME", "axl-test")
    AXL_PASSWORD = os.environ.get("AXL_PASSWORD", "")
    AXL_FQDN     = os.environ.get("AXL_FQDN", "")
    AXL_ADDRESS  = f"https://{AXL_FQDN}:8443/axl/"
    WSDL_PATH    = os.path.join(
        os.path.dirname(__file__),
        os.environ.get("WSDL_PATH", "schema/AXLAPI.wsdl")
    )
    AXL_BINDING  = "{http://www.cisco.com/AXLAPIService/}AXLAPIBinding"
    AXL_TIMEOUT  = 20

    # ── Upload ─────────────────────────────────────────────
    UPLOAD_FOLDER   = os.path.join(os.path.dirname(__file__), "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {"csv"}

    # ── Server ─────────────────────────────────────────────
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", 5000))
