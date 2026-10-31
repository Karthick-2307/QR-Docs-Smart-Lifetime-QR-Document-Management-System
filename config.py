import os
from urllib.parse import urlparse
import ipaddress
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def validate_production_url(url: str):
    """
    Validates that PUBLIC_BASE_URL is a permanent HTTPS domain in production.
    Refuses localhost, IP addresses, or non-HTTPS schemes.
    """
    if not url:
        raise ValueError("PUBLIC_BASE_URL must be specified.")
    
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(
            f"Invalid PUBLIC_BASE_URL in production: '{url}'. "
            "In production, PUBLIC_BASE_URL must use the HTTPS scheme (e.g. 'https://qrdocs.example.com')."
        )
    
    host = parsed.hostname
    if not host:
        raise ValueError(f"Invalid host in PUBLIC_BASE_URL: '{url}'.")
    
    if host in ("localhost", "127.0.0.1", "0.0.0.0"):
        raise ValueError(
            f"Invalid PUBLIC_BASE_URL in production: '{url}'. "
            "Localhost and loopback addresses are not permitted in production."
        )
    
    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False

    if is_ip:
        raise ValueError(
            f"Invalid PUBLIC_BASE_URL in production: '{url}'. "
            "IP addresses are not permitted in production. Use a permanent domain name."
        )

class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-insecure-secret-key-change-in-prod")
    FLASK_ENV = os.getenv("FLASK_ENV", os.getenv("ENV", "development"))
    IS_PRODUCTION = FLASK_ENV.lower() == "production"

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    # Database
    INSTANCE_DIR = os.getenv("INSTANCE_DIR", os.path.join(BASE_DIR, "instance"))
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "documents.db").replace(os.sep, "/")

    raw_db_url = os.getenv("DATABASE_URL")
    if not raw_db_url:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{DEFAULT_DB_PATH}"
    elif raw_db_url.startswith("sqlite:///") and not raw_db_url.startswith("sqlite:///:memory:"):
        path_part = raw_db_url[len("sqlite:///"):]
        # Check if relative path (not starting with Windows drive 'C:/' or Unix '/')
        is_windows_abs = len(path_part) > 1 and path_part[1] == ":"
        is_unix_abs = path_part.startswith("/")
        if not (is_windows_abs or is_unix_abs):
            abs_path = os.path.abspath(os.path.join(BASE_DIR, path_part)).replace(os.sep, "/")
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{abs_path}"
        else:
            SQLALCHEMY_DATABASE_URI = raw_db_url
    else:
        # Ensure postgresql+psycopg2 driver is specified for SQLAlchemy
        if raw_db_url.startswith("postgres://"):
            raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+"):
            raw_db_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        # Clean channel_binding parameter if present (prevents libpq driver incompatibilities)
        if "channel_binding=" in raw_db_url:
            import re
            raw_db_url = re.sub(r'[?&]channel_binding=[^&]+', '', raw_db_url)
            if '?' not in raw_db_url and '&' in raw_db_url:
                raw_db_url = raw_db_url.replace('&', '?', 1)
        SQLALCHEMY_DATABASE_URI = raw_db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Engine options: SQLite needs connect_args; PostgreSQL / MySQL use pool settings
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"timeout": 30, "check_same_thread": False}
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }

    # Uploads and QR code storage (configurable for Render Persistent Disks)
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    QR_FOLDER = os.getenv("QR_FOLDER", os.path.join(BASE_DIR, "generated_qr"))
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10 MB default
    MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE

    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
    }

    # Security & Sessions
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = IS_PRODUCTION
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Rate Limiting
    RATELIMIT_DEFAULT = "120 per minute"
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_KEY_PREFIX = "qr_docs"

    # Admin bootstrap
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    PUBLIC_BASE_URL = "http://testserver"
    IS_PRODUCTION = False
    RATELIMIT_ENABLED = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "instance", "test_uploads")
    QR_FOLDER = os.path.join(BASE_DIR, "instance", "test_qr")
