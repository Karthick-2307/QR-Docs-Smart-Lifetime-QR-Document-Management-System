# QR Docs – Smart Lifetime QR Document Management System

QR Docs is a secure, responsive, full-stack document management system built with Python, Flask, SQLAlchemy, SQLite (with WAL mode), and high-resolution deterministic QR code generation.

Each uploaded document receives an unpredictable, permanent public UUID4 identifier and an associated lifetime QR code. Public visitors can scan this QR code with their mobile phone's native camera or the application's built-in camera-based QR scanner to instantly access document details, preview PDFs and images inline, and download the original file.

---

## 1. Key Features

- **Lifetime QR Codes (Core Rule)**: Every QR code is permanent, immutable, and deterministic. It never expires, rotates, or changes—even when updating metadata, changing categories or tags, or replacing the underlying file.
- **Informational Expiry**: Document expiry dates are strictly informational. When an expiry date passes, the public page displays an "Expired" banner, but the document remains accessible and the QR code continues to resolve (HTTP 200).
- **Soft Deletion & Immediate Reactivation**: Deleting a document performs a soft-delete (`is_active = False`), immediately returning a standardized **HTTP 410 Gone** page. Administrators can reactivate the document with one click to restore the original QR code and public URL.
- **Permanent Tombstones**: Permanently deleting a document erases the physical file and QR image while recording the UUID in `RetiredPublicId`. The public ID is never reallocated to any future document, and requests return HTTP 410.
- **Built-in Camera Scanner & Image Uploader**: Uses the local vendored `html5-qrcode` library with camera selection, rear camera preference on mobile, and an image upload scanner fallback. Scanned URLs are securely validated against the host origin and `/document/<uuid>` pattern before redirection.
- **Printable Labels**: Generates formatted A4 sheets or compact sticker labels with document title, ID, QR code, and scanning instructions, styled with print-specific CSS (`print.css`).
- **Administrative Dashboard**:
  - Key metrics: Total Documents, Active QR Codes, Uploaded Today, Total Storage Used.
  - Search across title, description, public ID, author, and tags.
  - Multi-criteria filtering by category, file format (PDF, PNG, JPG), and lifecycle status.
  - Server-side pagination and responsive tables.
  - One-click "Regenerate All QR Images" maintenance tool.
- **Security Hardening**:
  - Scrypt password hashing with Werkzeug.
  - Rate-limited admin login (5 attempts per minute per IP).
  - CSRF protection across all forms and asynchronous fetch operations.
  - Strict upload validation: extension checking, MIME type verification, file signature magic byte inspection, and EXIF metadata stripping via Pillow.
  - Randomized stored filenames preventing directory traversal.
  - HTTP security headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: SAMEORIGIN`, Content Security Policy (CSP), and production HSTS.
  - Anonymized analytics: `ScanLog` logs timestamps and User-Agent strings but **strictly omits IP addresses**.

---

## 2. Technology Stack

- **Backend**: Python 3.11+, Flask, Flask-Login, Flask-WTF, Flask-Limiter, Werkzeug
- **Database**: SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL`), SQLAlchemy ORM, Flask-Migrate (Alembic)
- **QR Generation**: Python `qrcode` (Error Correction Level H, 4-module quiet zone, PNG output), Pillow
- **QR Scanner**: `html5-qrcode` JavaScript library (vendored locally in `static/js/`, no external CDN required)
- **UI / Frontend**: HTML5, CSS3, modern CSS variables, responsive desktop sidebar & mobile drawer, light/dark mode
- **Production Server**: Gunicorn (2–3 sync workers with SQLite WAL mode)
- **Testing**: pytest (23 automated unit and integration tests)

---

## 3. Project Directory Structure

```
qr_docs/
├── app.py                     # Application factory & CLI commands
├── config.py                  # Environment & production domain validation
├── extensions.py              # Flask extensions (db, login, csrf, limiter, migrate)
├── forms.py                   # Flask-WTF forms with CSRF protection
├── models.py                  # Admin, Document, ScanLog, RetiredPublicId
├── requirements.txt           # Pinned dependencies
├── .env.example               # Example environment configuration
├── .gitignore                 # Excludes instance, uploads, QR images, secrets
├── gunicorn.conf.py           # Production Gunicorn configuration
├── README.md                  # Comprehensive documentation
│
├── routes/
│   ├── __init__.py
│   ├── auth.py                # Admin login & logout
│   ├── admin.py               # Dashboard, upload, edit, replace, delete, labels
│   ├── documents.py           # Public document view, file streaming, QR serving
│   └── scanner.py             # QR camera scanner & URL validation API
│
├── services/
│   ├── __init__.py            # Service accessors
│   ├── document_service.py    # CRUD, soft delete, search & filter, analytics
│   ├── qr_service.py          # Deterministic QR generation & auto-regeneration
│   └── storage_service.py     # Magic byte validation, EXIF stripping, disk storage
│
├── templates/
│   ├── base.html              # Base template with theme toggle & navbar
│   ├── index.html             # Public landing page
│   ├── auth/
│   │   └── login.html         # Admin login
│   ├── admin/
│   │   ├── base_admin.html    # Dashboard layout with sidebar navigation
│   │   ├── dashboard.html     # Stats cards & recent documents table
│   │   ├── documents.html     # Search, filter, and paginated documents list
│   │   ├── upload.html        # Drag-and-drop upload form
│   │   ├── upload_success.html# Post-upload QR view and quick actions
│   │   ├── edit.html          # Metadata edit, file replace, lifecycle controls
│   │   ├── qr_manager.html    # QR code gallery & batch tools
│   │   ├── label.html         # Printable A4 & compact QR labels
│   │   └── settings.html      # Password change, base URL view, regenerate all
│   ├── public/
│   │   └── document.html      # Public document page & embedded viewer
│   ├── scanner/
│   │   └── scanner.html       # Camera-based QR scanner & image fallback
│   └── errors/
│       ├── 404.html           # Professional Not Found page
│       ├── 410.html           # Professional 410 Gone page
│       └── 500.html           # Server error page
│
├── static/
│   ├── css/
│   │   ├── style.css          # Design system & CSS variables (light/dark)
│   │   ├── dashboard.css      # Sidebar, cards, dropzone, responsive drawer
│   │   └── print.css          # Print-only rules for stickers and sheets
│   ├── js/
│   │   ├── main.js            # Theme toggle, clipboard, modal helpers
│   │   ├── upload.js          # Drag & drop, validation, preview, progress
│   │   ├── scanner.js         # Camera lifecycle, frame reticle, API validation
│   │   └── html5-qrcode.min.js# Vendored client-side QR decoder
│   └── images/
│       └── logo.svg           # Vector application logo
│
├── instance/                  # SQLite database location (gitignored)
├── uploads/                   # Sanitized document storage (gitignored)
├── generated_qr/              # Deterministic QR PNG images (gitignored)
├── migrations/                # Alembic database migration scripts
└── tests/
    ├── conftest.py            # Test fixtures, mock files, test client
    ├── test_auth.py           # Login, logout, rate limits, production checks
    ├── test_documents.py      # Uploads, validation, 410/404, file streaming
    └── test_qr.py             # Byte-identical QR invariance & regeneration
```

---

## 4. Prerequisites

- **Python**: Version 3.11 or higher
- **Operating System**: Linux Mint, Ubuntu 22.04/24.04 LTS, macOS, or Windows
- **System packages** (Ubuntu / Linux Mint):
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip git
  ```

---

## 5. Installation & Setup Instructions

### Step 1: Clone or Navigate to the Project

```bash
cd qr_docs
```

### Step 2: Create and Activate Virtual Environment

**On Linux Mint / Ubuntu / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. Environment Configuration

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```ini
# Flask Secret Key (use a secure random string in production)
FLASK_SECRET_KEY=generate-a-strong-random-key-here

# Environment Mode: 'development' or 'production'
FLASK_ENV=development

# Permanent Public Base URL encoded into all QR codes
# Note: In production, this MUST be an HTTPS domain name (e.g. https://qrdocs.example.com)
PUBLIC_BASE_URL=http://127.0.0.1:5000

# Database Storage URI
DATABASE_URL=sqlite:///instance/documents.db

# Max File Upload Limit in Bytes (10485760 = 10 MB)
MAX_UPLOAD_SIZE=10485760

# Optional one-time bootstrap admin credentials (used only on first startup if no admin exists)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ChangeThisPassword123!
```

---

## 7. Database Initialization & Admin Setup

### Initialize Database Schema

```bash
flask db upgrade
```
*(Alternatively, starting the application will automatically create all missing tables if running for the first time).*

### Create Administrator Account

Use the dedicated interactive CLI command:

```bash
flask create-admin
```
You will be prompted to enter a username and password.

---

## 8. Running the Application

### Development Server

```bash
flask run --host=0.0.0.0 --port=5000
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### Production Server (Linux / Ubuntu / Mint)

Run Gunicorn using the production configuration:

```bash
gunicorn -c gunicorn.conf.py "app:create_app()"
```

---

## 9. Automated Testing

Run the full pytest test suite:

```bash
pytest -v tests
```

### Verified Test Matrix:
- `test_admin_login_success`: Validates successful admin authentication.
- `test_admin_login_failure`: Validates rejection of bad credentials.
- `test_unauthorized_access_redirects`: Ensures protected admin pages require authentication.
- `test_admin_logout`: Validates session termination.
- `test_cli_create_admin`: Verifies `flask create-admin` CLI command.
- `test_change_password_in_settings`: Verifies password updates.
- `test_production_refuses_localhost_or_ip`: Asserts that production mode halts if `PUBLIC_BASE_URL` is localhost, an IP address, or non-HTTPS.
- `test_document_upload_pdf`: Verifies PDF upload and metadata recording.
- `test_invalid_file_extension_rejection`: Rejects forbidden file extensions (`.exe`, `.sh`).
- `test_fake_extension_signature_mismatch`: Rejects files disguised as PDFs through magic byte checking.
- `test_file_size_rejection`: Rejects files exceeding the configured maximum size.
- `test_public_document_view_and_download`: Confirms public page loading and file streaming.
- `test_document_expiry_informational`: Confirms expired documents return HTTP 200 with an Expired banner.
- `test_soft_delete_and_reactivation`: Verifies 410 Gone on deactivation and restoration upon reactivation.
- `test_permanent_deletion_and_retired_tombstone`: Confirms file deletion, tombstone insertion, and permanent 410 status.
- `test_invalid_document_id_returns_404`: Confirms 404 for unknown UUIDs.
- `test_scanner_url_validation`: Verifies scanner security filters.
- `test_document_upload_image_and_exif_strip`: Verifies image processing and EXIF stripping.
- `test_search_and_filter_documents`: Tests query search and category filters.
- `test_qr_generation_and_url_correctness`: Verifies canonical QR URL encoding.
- `test_qr_png_byte_identical_across_operations`: **Guarantees 100% byte-identical QR output across metadata edits, file replacements, deactivation/reactivation cycles, and disk deletions followed by regeneration.**
- `test_admin_download_qr_route`: Verifies admin QR image delivery.
- `test_regenerate_all_qr_action`: Verifies bulk QR re-creation.

---

## 10. Lifetime QR Policy, Domain Changes & Backups

### Lifetime QR Policy
- Documents receive a random UUID4 `public_id` that never changes.
- The QR encodes only `{PUBLIC_BASE_URL}/document/{public_id}`.
- Metadata edits, category changes, author updates, or file replacements **never modify the QR code**.
- If a QR PNG file is accidentally deleted from disk, the system regenerates the **exact same byte-identical image** on demand.

### Domain Change Warning
- Physical QR codes printed on paper, stickers, or metal badges encode the domain in use when printed.
- If you change `PUBLIC_BASE_URL` in the future, previously printed QR codes will still direct to the old domain.
- **Guideline**: When changing domains, keep the legacy domain active with a permanent HTTP 301 redirect:
  ```nginx
  server {
      server_name old-domain.com;
      return 301 https://new-domain.com$request_uri;
  }
  ```

### Backup Guidance
Because QR codes are permanent, maintain durable backups of:
1. `instance/documents.db` (Database)
2. `uploads/` (Uploaded document files)
3. `generated_qr/` (QR image files)

---

## 11. Security Architecture

1. **Password Hashing**: Uses modern Werkzeug scrypt hashing with automatic per-user salts.
2. **CSRF Protection**: All form submissions and asynchronous fetch requests must present a valid CSRF token.
3. **Session Cookies**: Marked `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
4. **File Content Validation**: Uploaded files are checked against allowed extensions, MIME types, and binary file signatures (magic bytes). Images are re-encoded through Pillow to strip malicious EXIF payloads.
5. **No Direct Directory Browsing**: Uploads and QR directories are stored outside public static directories and delivered exclusively via validated Flask route controllers.
6. **No IP Logging in Analytics**: `ScanLog` records view timestamps and User-Agents for analytics, but **never stores client IP addresses**.
7. **Rate Limiting**: Administrator login is capped at 5 attempts per minute per IP to block brute-force attempts.
8. **Public Document Scope**: Public URLs are accessible to anyone possessing their link. Documents intended for public access should not contain confidential server secrets.

---

## 12. Troubleshooting

### Camera access fails in the QR Scanner
- Modern browsers enforce camera permissions only over secure origins (`https://` or `http://localhost`). Ensure you are using HTTPS in production or localhost during local development.
- Check that the browser has been granted camera permissions in site settings.
- If no camera is attached, use the built-in **Scan From Image File** fallback button.

### "Database is locked" error
- SQLite WAL mode is enabled automatically on startup (`PRAGMA journal_mode=WAL`).
- Ensure Gunicorn is configured with 2–3 sync workers as specified in `gunicorn.conf.py`.

### Application refuses to start in Production
- If `FLASK_ENV=production` is set, `PUBLIC_BASE_URL` must be a valid HTTPS domain (e.g. `https://docs.mycompany.com`). Localhost, loopback IPs (`127.0.0.1`), and raw IP addresses are intentionally rejected.

