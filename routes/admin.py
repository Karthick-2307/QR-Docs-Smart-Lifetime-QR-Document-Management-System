from datetime import datetime, timezone
from functools import wraps
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import Document, Admin, ScanLog, RetiredPublicId, utc_now
from forms import (
    DocumentUploadForm,
    DocumentEditForm,
    DocumentReplaceFileForm,
    ChangePasswordForm,
    SubAdminCreateForm,
    SubAdminEditForm,
    EmptyForm,
)
from services import get_document_service, get_qr_service, get_storage_service
from services.storage_service import StorageValidationError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def require_main_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_main_admin:
            flash("Access restricted: Only the Main Admin can manage administrator and sub-admin accounts.", "danger")
            return redirect(url_for("admin.dashboard"))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.before_request
@login_required
def require_admin_login():
    pass

@admin_bp.route("/dashboard")
@admin_bp.route("/")
def dashboard():
    today = datetime.now(timezone.utc).date()
    total_docs = Document.query.count()
    active_qrs = Document.query.filter_by(is_active=True).count()
    
    # Uploaded today
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    uploaded_today = Document.query.filter(Document.uploaded_at >= today_start).count()
    
    # Total storage used in bytes
    total_storage_bytes = db.session.query(func.coalesce(func.sum(Document.file_size), 0)).scalar()

    # Recent 8 documents
    recent_docs = Document.query.order_by(Document.uploaded_at.desc()).limit(8).all()
    
    empty_form = EmptyForm()

    return render_template(
        "admin/dashboard.html",
        total_docs=total_docs,
        active_qrs=active_qrs,
        uploaded_today=uploaded_today,
        total_storage_bytes=total_storage_bytes,
        recent_docs=recent_docs,
        empty_form=empty_form,
    )

@admin_bp.route("/documents")
def documents_list():
    query_str = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip() or None
    file_type = request.args.get("file_type", "").strip() or None
    status = request.args.get("status", "").strip() or None
    date_from = request.args.get("date_from", "").strip() or None
    date_to = request.args.get("date_to", "").strip() or None
    sort_by = request.args.get("sort_by", "newest")
    page = request.args.get("page", 1, type=int)

    doc_service = get_document_service()
    pagination = doc_service.search_and_filter(
        query_str=query_str,
        category=category,
        file_type=file_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        page=page,
        per_page=10,
    )

    # Categories for filter dropdown
    categories = [
        c[0] for c in db.session.query(Document.category).filter(Document.category.isnot(None)).distinct().all() if c[0]
    ]

    empty_form = EmptyForm()

    return render_template(
        "admin/documents.html",
        pagination=pagination,
        categories=categories,
        query_str=query_str,
        current_category=category,
        current_file_type=file_type,
        current_status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        empty_form=empty_form,
    )

@admin_bp.route("/upload", methods=["GET", "POST"])
def upload():
    form = DocumentUploadForm()
    if form.validate_on_submit():
        doc_service = get_document_service()
        try:
            doc = doc_service.create_document(
                title=form.title.data,
                file_storage=form.file.data,
                public_base_url=current_app.config["PUBLIC_BASE_URL"],
                description=form.description.data,
                category=form.category.data,
                tags=form.tags.data,
                author=form.author.data,
                document_date=form.document_date.data.strftime("%Y-%m-%d") if form.document_date.data else None,
                expiry_date=form.expiry_date.data.strftime("%Y-%m-%d") if form.expiry_date.data else None,
                certificate_code=form.certificate_code.data if hasattr(form, 'certificate_code') else None,
            )
            flash(f"Document '{doc.title}' uploaded successfully! QR code generated.", "success")
            return redirect(url_for("admin.upload_success", public_id=doc.public_id))
        except StorageValidationError as e:
            flash(f"Upload error: {str(e)}", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred during upload: {str(e)}", "danger")

    return render_template("admin/upload.html", form=form)

@admin_bp.route("/upload/success/<public_id>")
def upload_success(public_id):
    doc = Document.query.filter_by(public_id=public_id).first_or_404()
    qr_service = get_qr_service()
    public_url = qr_service.get_public_url(doc.public_id, current_app.config["PUBLIC_BASE_URL"])
    # Ensure QR exists
    qr_service.get_or_regenerate_qr(doc.public_id, current_app.config["PUBLIC_BASE_URL"])
    return render_template("admin/upload_success.html", document=doc, public_url=public_url)

@admin_bp.route("/document/<public_id>/edit", methods=["GET", "POST"])
def edit_document(public_id):
    doc = Document.query.filter_by(public_id=public_id).first_or_404()
    form = DocumentEditForm(obj=doc)
    replace_form = DocumentReplaceFileForm()

    if form.validate_on_submit():
        doc_service = get_document_service()
        doc_service.update_metadata(
            document=doc,
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            tags=form.tags.data,
            author=form.author.data,
            document_date=form.document_date.data.strftime("%Y-%m-%d") if form.document_date.data else None,
            expiry_date=form.expiry_date.data.strftime("%Y-%m-%d") if form.expiry_date.data else None,
            certificate_code=form.certificate_code.data if hasattr(form, 'certificate_code') else None,
        )
        flash("Document metadata updated successfully. The QR code and public URL remain unchanged.", "success")
        return redirect(url_for("admin.edit_document", public_id=doc.public_id))

    return render_template("admin/edit.html", form=form, replace_form=replace_form, document=doc)

@admin_bp.route("/document/<public_id>/replace-file", methods=["POST"])
def replace_document_file(public_id):
    doc = Document.query.filter_by(public_id=public_id).first_or_404()
    form = DocumentReplaceFileForm()
    if form.validate_on_submit():
        doc_service = get_document_service()
        try:
            doc_service.replace_file(doc, form.file.data)
            flash("File replaced successfully! Public ID and QR code remain intact.", "success")
        except StorageValidationError as e:
            flash(f"File replacement failed: {str(e)}", "danger")
        except Exception as e:
            flash(f"Error replacing file: {str(e)}", "danger")
    else:
        flash("Invalid file submission.", "danger")

    return redirect(url_for("admin.edit_document", public_id=doc.public_id))

@admin_bp.route("/document/<public_id>/deactivate", methods=["POST"])
def deactivate_document(public_id):
    form = EmptyForm()
    if form.validate_on_submit():
        doc = Document.query.filter_by(public_id=public_id).first_or_404()
        doc_service = get_document_service()
        doc_service.deactivate_document(doc)
        flash(f"Document '{doc.title}' has been deactivated. The public URL will now return 410 Gone.", "warning")
    return redirect(request.referrer or url_for("admin.documents_list"))

@admin_bp.route("/document/<public_id>/reactivate", methods=["POST"])
def reactivate_document(public_id):
    form = EmptyForm()
    if form.validate_on_submit():
        doc = Document.query.filter_by(public_id=public_id).first_or_404()
        doc_service = get_document_service()
        doc_service.reactivate_document(doc)
        flash(f"Document '{doc.title}' has been reactivated. The QR code works again.", "success")
    return redirect(request.referrer or url_for("admin.documents_list"))

@admin_bp.route("/document/<public_id>/delete", methods=["POST"])
def delete_document(public_id):
    form = EmptyForm()
    if form.validate_on_submit():
        doc = Document.query.filter_by(public_id=public_id).first_or_404()
        title = doc.title
        doc_service = get_document_service()
        doc_service.permanently_delete_document(doc)
        flash(
            f"Document '{title}' was permanently deleted. Its public ID has been retired as a tombstone and will never be reused.",
            "info"
        )
    return redirect(url_for("admin.documents_list"))

@admin_bp.route("/qr-manager")
def qr_manager():
    page = request.args.get("page", 1, type=int)
    query_str = request.args.get("q", "").strip()
    
    query = Document.query
    if query_str:
        term = f"%{query_str}%"
        query = query.filter(Document.title.ilike(term) | Document.public_id.ilike(term))
    
    pagination = query.order_by(Document.uploaded_at.desc()).paginate(page=page, per_page=12, error_out=False)
    
    qr_service = get_qr_service()
    base_url = current_app.config["PUBLIC_BASE_URL"]
    for doc in pagination.items:
        qr_service.get_or_regenerate_qr(doc.public_id, base_url)

    return render_template(
        "admin/qr_manager.html",
        pagination=pagination,
        query_str=query_str,
        base_url=base_url
    )

@admin_bp.route("/document/<public_id>/label")
def printable_label(public_id):
    doc = Document.query.filter_by(public_id=public_id).first_or_404()
    qr_service = get_qr_service()
    base_url = current_app.config["PUBLIC_BASE_URL"]
    public_url = qr_service.get_public_url(doc.public_id, base_url)
    qr_service.get_or_regenerate_qr(doc.public_id, base_url)
    layout = request.args.get("layout", "a4")  # 'a4' or 'compact'
    return render_template("admin/label.html", document=doc, public_url=public_url, layout=layout)

@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    form = ChangePasswordForm()
    empty_form = EmptyForm()

    if request.method == "GET":
        form.display_name.data = current_user.display_name or ""

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            if form.display_name.data:
                current_user.display_name = form.display_name.data.strip()
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Administrator password updated successfully.", "success")
            return redirect(url_for("admin.settings"))

    return render_template(
        "admin/settings.html",
        form=form,
        empty_form=empty_form,
        public_base_url=current_app.config["PUBLIC_BASE_URL"],
        is_production=current_app.config.get("IS_PRODUCTION", False),
    )

# --- Sub-Admin Management (Main Admin Exclusive) ---

@admin_bp.route("/users")
@require_main_admin
def users_list():
    admins = Admin.query.order_by(Admin.role.asc(), Admin.created_at.desc()).all()
    empty_form = EmptyForm()
    return render_template("admin/users.html", admins=admins, empty_form=empty_form)

@admin_bp.route("/users/create", methods=["GET", "POST"])
@require_main_admin
def user_create():
    form = SubAdminCreateForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if Admin.query.filter_by(username=username).first():
            flash(f"An administrator account with username '{username}' already exists.", "danger")
        else:
            new_admin = Admin(
                username=username,
                display_name=form.display_name.data.strip(),
                role=form.role.data,
            )
            new_admin.set_password(form.password.data)
            db.session.add(new_admin)
            db.session.commit()
            role_desc = "Main Admin" if new_admin.role == "admin" else "Sub Admin"
            flash(f"{role_desc} '{new_admin.name_display}' created successfully.", "success")
            return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", form=form, title="Create Admin / Sub Admin")

@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@require_main_admin
def user_edit(user_id):
    target = db.session.get(Admin, user_id)
    if not target:
        flash("Administrator account not found.", "danger")
        return redirect(url_for("admin.users_list"))
    form = SubAdminEditForm(obj=target)

    if form.validate_on_submit():
        new_username = form.username.data.strip()
        existing = Admin.query.filter_by(username=new_username).first()
        if existing and existing.id != target.id:
            flash(f"Username '{new_username}' is already taken.", "danger")
        else:
            target.username = new_username
            target.display_name = form.display_name.data.strip()
            
            # Prevent demoting the only main admin if it's the current user
            if target.id == current_user.id and form.role.data != "admin":
                flash("You cannot demote your own Main Admin account.", "danger")
            else:
                target.role = form.role.data

            if form.new_password.data and form.new_password.data.strip():
                target.set_password(form.new_password.data.strip())

            db.session.commit()
            flash(f"Account '{target.name_display}' updated successfully.", "success")
            return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", form=form, title=f"Edit Account: {target.name_display}", target=target)

@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_main_admin
def user_delete(user_id):
    form = EmptyForm()
    if form.validate_on_submit():
        target = db.session.get(Admin, user_id)
        if not target:
            flash("Administrator account not found.", "danger")
            return redirect(url_for("admin.users_list"))
        if target.id == current_user.id:
            flash("You cannot delete your own Main Admin account.", "danger")
            return redirect(url_for("admin.users_list"))

        name = target.name_display
        role_label = target.role_label
        db.session.delete(target)
        db.session.commit()
        flash(f"{role_label.title()} '{name}' has been deleted successfully.", "success")
    return redirect(url_for("admin.users_list"))

@admin_bp.route("/settings/regenerate-all-qr", methods=["POST"])
def regenerate_all_qr():
    form = EmptyForm()
    if form.validate_on_submit():
        qr_service = get_qr_service()
        base_url = current_app.config["PUBLIC_BASE_URL"]
        docs = Document.query.all()
        count = 0
        for doc in docs:
            qr_service.generate_and_save_qr(doc.public_id, base_url)
            count += 1
        flash(
            f"Successfully regenerated {count} QR code images. Note: Already-printed physical QR codes will still point to whichever URL was encoded at printing time.",
            "warning"
        )
    return redirect(url_for("admin.settings"))

