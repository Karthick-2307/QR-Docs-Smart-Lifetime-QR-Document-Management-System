from datetime import datetime, timezone
import uuid
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event
from sqlalchemy.engine import Engine
from extensions import db

# Enable WAL mode and foreign key constraints on SQLite engines
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        finally:
            cursor.close()

def utc_now():
    return datetime.now(timezone.utc)

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), default="admin", nullable=False)  # 'admin' (main admin) or 'sub_admin'
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    @property
    def is_main_admin(self) -> bool:
        return self.role == "admin"

    @property
    def role_label(self) -> str:
        return "admin" if self.role == "admin" else "sub admin"

    @property
    def name_display(self) -> str:
        return self.display_name if self.display_name else self.username

    def set_password(self, password: str):
        # Uses Werkzeug's secure hashing (scrypt by default on modern Python)
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Admin {self.username} ({self.role})>"

class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    certificate_code = db.Column(db.String(50), unique=True, nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    tags = db.Column(db.String(255), nullable=True)  # Comma-separated normalized tags
    author = db.Column(db.String(150), nullable=True)
    document_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)  # Informational only

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_extension = db.Column(db.String(10), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    file_data = db.Column(db.LargeBinary, nullable=True)  # Online binary persistence for zero-data-loss cloud hosting

    uploaded_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    scans = db.relationship("ScanLog", backref="document", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def masked_id(self) -> str:
        """Returns clean 4-digit or formatted certificate ID for verification."""
        if self.certificate_code:
            return self.certificate_code
        # Generate 4-digit code from UUID for consistent display
        digits = ''.join(c for c in self.public_id if c.isdigit())
        four_d = digits[:4] if len(digits) >= 4 else "2026"
        return f"THX-{four_d}"

    @property
    def four_digit_code(self) -> str:
        """Returns concise 4-digit code."""
        if self.certificate_code and len(self.certificate_code) == 4 and self.certificate_code.isdigit():
            return self.certificate_code
        digits = ''.join(c for c in self.public_id if c.isdigit())
        return digits[:4] if len(digits) >= 4 else "2026"

    @property
    def is_expired(self) -> bool:
        if not self.expiry_date:
            return False
        from datetime import date
        current_date = max(datetime.now(timezone.utc).date(), date.today())
        return self.expiry_date < current_date

    def get_tags_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def __repr__(self):
        return f"<Document {self.public_id} - {self.title}>"

class ScanLog(db.Model):
    __tablename__ = "scan_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    scanned_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    user_agent = db.Column(db.String(512), nullable=True)
    # Strictly DO NOT store IP addresses per requirement

    def __repr__(self):
        return f"<ScanLog doc_id={self.document_id} at {self.scanned_at}>"

class RetiredPublicId(db.Model):
    __tablename__ = "retired_public_ids"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    retired_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    reason = db.Column(db.String(100), default="permanently_deleted", nullable=False)

    def __repr__(self):
        return f"<RetiredPublicId {self.public_id}>"
