import os
import io
from flask import (
    Blueprint,
    render_template,
    abort,
    send_file,
    request,
    current_app,
    jsonify,
)
from flask_login import login_required
from services import get_document_service, get_storage_service, get_qr_service

documents_bp = Blueprint("documents", __name__)

@documents_bp.route("/api/verify/<identifier>")
def api_verify_document(identifier):
    identifier = identifier.strip()
    doc_service = get_document_service()
    doc, status = doc_service.lookup_public_document(identifier)

    if status in ("retired", "inactive"):
        return jsonify({
            "success": False,
            "status": status,
            "error": "This document or certificate has been deactivated or retired."
        }), 410

    if status == "not_found" or not doc:
        return jsonify({
            "success": False,
            "status": "not_found",
            "error": "No certificate or document found with this ID."
        }), 404

    date_str = ""
    if doc.document_date:
        date_str = doc.document_date.strftime("%Y-%m")
    elif doc.uploaded_at:
        date_str = doc.uploaded_at.strftime("%Y-%m")

    return jsonify({
        "success": True,
        "status": "active",
        "document": {
            "public_id": doc.public_id,
            "masked_id": doc.masked_id,
            "four_digit_code": doc.four_digit_code,
            "title": doc.title,
            "author": doc.author or "",
            "category": doc.category or "Certified Document",
            "date": date_str,
            "is_expired": doc.is_expired,
            "expiry_date": doc.expiry_date.strftime("%Y-%m-%d") if doc.expiry_date else None,
            "file_type": doc.file_extension.upper(),
            "file_url": f"/document/{doc.public_id}/file",
            "download_url": f"/document/{doc.public_id}/download"
        }
    })

@documents_bp.route("/document/<public_id>")
def view_public_document(public_id):
    doc_service = get_document_service()
    doc, status = doc_service.lookup_public_document(public_id)

    if status in ("retired", "inactive"):
        return render_template("errors/410.html", public_id=public_id), 410
    if status == "not_found" or not doc:
        return render_template("errors/404.html", public_id=public_id), 404

    # Log scan for analytics (omits IP address)
    user_agent = request.headers.get("User-Agent")
    doc_service.log_scan(doc, user_agent)

    return render_template("public/document.html", document=doc)

@documents_bp.route("/document/<public_id>/file")
def view_document_file(public_id):
    doc_service = get_document_service()
    doc, status = doc_service.lookup_public_document(public_id)

    if status in ("retired", "inactive"):
        return render_template("errors/410.html", public_id=public_id), 410
    if status == "not_found" or not doc:
        return render_template("errors/404.html", public_id=public_id), 404

    storage = get_storage_service()
    filepath = storage.get_file_path(doc.stored_filename)

    if os.path.exists(filepath):
        return send_file(
            filepath,
            mimetype=doc.mime_type,
            as_attachment=False,
            download_name=doc.original_filename,
        )

    # Cloud fallback: restore directly from database binary data
    if doc.file_data:
        try:
            with open(filepath, "wb") as f:
                f.write(doc.file_data)
        except Exception:
            pass
        return send_file(
            io.BytesIO(doc.file_data),
            mimetype=doc.mime_type,
            as_attachment=False,
            download_name=doc.original_filename,
        )

    abort(404)

@documents_bp.route("/document/<public_id>/download")
def download_document_file(public_id):
    doc_service = get_document_service()
    doc, status = doc_service.lookup_public_document(public_id)

    if status in ("retired", "inactive"):
        return render_template("errors/410.html", public_id=public_id), 410
    if status == "not_found" or not doc:
        return render_template("errors/404.html", public_id=public_id), 404

    storage = get_storage_service()
    filepath = storage.get_file_path(doc.stored_filename)

    if os.path.exists(filepath):
        return send_file(
            filepath,
            mimetype=doc.mime_type,
            as_attachment=True,
            download_name=doc.original_filename,
        )

    # Cloud fallback: restore directly from database binary data
    if doc.file_data:
        try:
            with open(filepath, "wb") as f:
                f.write(doc.file_data)
        except Exception:
            pass
        return send_file(
            io.BytesIO(doc.file_data),
            mimetype=doc.mime_type,
            as_attachment=True,
            download_name=doc.original_filename,
        )

    abort(404)

@documents_bp.route("/qr/<public_id>.png")
@login_required
def serve_qr_image(public_id):
    """
    Serves the QR code PNG image for a document. Admin-only per specifications.
    """
    qr_service = get_qr_service()
    base_url = current_app.config["PUBLIC_BASE_URL"]
    filepath = qr_service.get_or_regenerate_qr(public_id, base_url)

    if not os.path.exists(filepath):
        abort(404)

    return send_file(filepath, mimetype="image/png")

