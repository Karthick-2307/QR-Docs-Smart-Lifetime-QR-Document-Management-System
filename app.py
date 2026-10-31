import os
import click
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_login import current_user

from config import Config, validate_production_url
from extensions import db, migrate, login_manager, csrf, limiter
from models import Admin
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.documents import documents_bp
from routes.scanner import scanner_bp

def create_app(config_class=None):
    if config_class is None:
        config_class = Config

    # Ensure working directory is always anchored to base directory
    try:
        os.chdir(config_class.BASE_DIR)
    except Exception:
        pass

    app = Flask(__name__)
    app.config.from_object(config_class)

    # In production, enforce HTTPS and permanent domain check
    if app.config.get("IS_PRODUCTION"):
        validate_production_url(app.config.get("PUBLIC_BASE_URL"))

    # Ensure required folders exist
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)
    os.makedirs(app.config.get("QR_FOLDER", "generated_qr"), exist_ok=True)
    os.makedirs(app.config.get("INSTANCE_DIR", "instance"), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Admin, int(user_id))

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(scanner_bp)

    # Root route
    @app.route("/")
    def index():
        verify_id = request.args.get("verifyId") or request.args.get("verify_id")
        if verify_id:
            return redirect(url_for("documents.view_public_document", public_id=verify_id.strip()))
        if current_user.is_authenticated:
            return redirect(url_for("admin.dashboard"))
        return render_template("index.html")

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        
        # CSP allowing self-hosted scripts, safe assets, Google Fonts, and thiranex.in
        csp = (
            "default-src 'self' https://www.thiranex.in https://thiranex.in; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob: https://www.thiranex.in https://thiranex.in; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "frame-src 'self' https://www.thiranex.in https://thiranex.in; "
            "object-src 'self'; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp

        if app.config.get("IS_PRODUCTION"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(410)
    def gone_error(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "This document is no longer available"}), 410
        return render_template("errors/410.html"), 410

    @app.errorhandler(413)
    def file_too_large(error):
        if request.is_json:
            return jsonify({"error": "File size exceeds the permitted limit."}), 413
        return render_template(
            "errors/500.html",
            title="File Too Large",
            message="The uploaded file exceeds the maximum allowed upload size limit."
        ), 413

    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.is_json:
            return jsonify({"error": "Too many requests. Please slow down."}), 429
        return render_template(
            "errors/500.html",
            title="Rate Limit Exceeded",
            message="Too many requests. Please wait a few moments and try again."
        ), 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    # CLI command: flask create-admin
    @app.cli.command("create-admin")
    @click.option("--username", prompt="Admin username", help="Username for administrator")
    @click.option("--name", default="", help="Custom display name (e.g. Manoj S)")
    @click.option("--role", default="admin", type=click.Choice(["admin", "sub_admin"]), help="Role ('admin' or 'sub_admin')")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password for administrator")
    def create_admin_command(username, name, role, password):
        """Create or update an administrator account."""
        username = username.strip()
        if not username:
            click.echo("Error: Username cannot be blank.")
            return

        admin = Admin.query.filter_by(username=username).first()
        if admin:
            admin.set_password(password)
            if name.strip():
                admin.display_name = name.strip()
            admin.role = role
            db.session.commit()
            click.echo(f"Updated administrator '{username}' ({role}).")
        else:
            new_admin = Admin(
                username=username,
                display_name=name.strip() if name.strip() else username,
                role=role
            )
            new_admin.set_password(password)
            db.session.add(new_admin)
            db.session.commit()
            click.echo(f"Administrator '{username}' ({role}) created successfully.")

    # One-time bootstrap check if database exists and admin env variables are set
    with app.app_context():
        try:
            db.create_all()
            # Safety checks to add columns to existing SQLite DB
            import sqlalchemy as sa
            with db.engine.connect() as conn:
                try:
                    conn.execute(sa.text("ALTER TABLE documents ADD COLUMN certificate_code VARCHAR(50)"))
                    conn.commit()
                except Exception:
                    pass

                try:
                    conn.execute(sa.text("ALTER TABLE admins ADD COLUMN display_name VARCHAR(100)"))
                    conn.commit()
                except Exception:
                    pass

                try:
                    conn.execute(sa.text("ALTER TABLE admins ADD COLUMN role VARCHAR(20) DEFAULT 'admin'"))
                    conn.commit()
                except Exception:
                    pass

                try:
                    conn.execute(sa.text("ALTER TABLE documents ADD COLUMN file_data BYTEA"))
                    conn.commit()
                except Exception:
                    try:
                        conn.execute(sa.text("ALTER TABLE documents ADD COLUMN file_data BLOB"))
                        conn.commit()
                    except Exception:
                        pass

            bootstrap_user = app.config.get("ADMIN_USERNAME")
            bootstrap_pass = app.config.get("ADMIN_PASSWORD")
            if bootstrap_user and bootstrap_pass:
                if Admin.query.count() == 0:
                    admin = Admin(
                        username=bootstrap_user.strip(),
                        display_name="Main Admin",
                        role="admin"
                    )
                    admin.set_password(bootstrap_pass)
                    db.session.add(admin)
                    db.session.commit()
                    app.logger.info("Bootstrap administrator account created from environment.")
                else:
                    # Ensure first admin is main admin
                    first_admin = Admin.query.first()
                    if first_admin and not first_admin.role:
                        first_admin.role = "admin"
                        db.session.commit()
        except Exception:
            pass

    return app

# Expose WSGI application callable for Gunicorn ('gunicorn app:app')
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

