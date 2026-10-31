import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import or_, desc, asc

from extensions import db
from models import Document, ScanLog, RetiredPublicId, utc_now
from services.storage_service import StorageService, StorageValidationError
from services.qr_service import QRService

class DocumentService:
    def __init__(self, storage_service: StorageService, qr_service: QRService):
        self.storage = storage_service
        self.qr = qr_service

    def _generate_unique_public_id(self) -> str:
        """
        Generates a fresh UUID4 public_id that has never been used,
        not even as a tombstone in RetiredPublicId.
        """
        while True:
            candidate = str(uuid.uuid4())
            # Check active documents
            if Document.query.filter_by(public_id=candidate).first():
                continue
            # Check retired tombstones
            if RetiredPublicId.query.filter_by(public_id=candidate).first():
                continue
            return candidate

    def create_document(
        self,
        title: str,
        file_storage,
        public_base_url: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        author: Optional[str] = None,
        document_date: Optional[str] = None,
        expiry_date: Optional[str] = None,
        certificate_code: Optional[str] = None,
    ) -> Document:
        orig_name, ext, mime_type, file_size, processed_bytes = self.storage.validate_and_process_upload(file_storage)
        
        stored_filename = self.storage.save_file(processed_bytes, ext)
        public_id = self._generate_unique_public_id()

        # Generate or assign 4-digit masked certificate code
        if certificate_code and certificate_code.strip():
            final_code = certificate_code.strip().upper()
        else:
            digits = ''.join(c for c in public_id if c.isdigit())
            four_d = digits[:4] if len(digits) >= 4 else "2026"
            final_code = f"THX-{four_d}"

        # Parse dates safely
        doc_date_obj = None
        if document_date:
            try:
                doc_date_obj = datetime.strptime(document_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass

        exp_date_obj = None
        if expiry_date:
            try:
                exp_date_obj = datetime.strptime(expiry_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass

        # Normalize tags
        normalized_tags = None
        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
            normalized_tags = ", ".join(sorted(set(tag_list)))

        document = Document(
            public_id=public_id,
            certificate_code=final_code,
            title=title.strip(),
            description=description.strip() if description else None,
            category=category.strip() if category else None,
            tags=normalized_tags,
            author=author.strip() if author else None,
            document_date=doc_date_obj,
            expiry_date=exp_date_obj,
            original_filename=orig_name,
            stored_filename=stored_filename,
            file_extension=ext,
            mime_type=mime_type,
            file_size=file_size,
            file_data=processed_bytes,
            is_active=True,
        )

        db.session.add(document)
        db.session.commit()

        # Generate QR code immediately
        self.qr.generate_and_save_qr(public_id, public_base_url)

        return document

    def update_metadata(
        self,
        document: Document,
        title: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        author: Optional[str] = None,
        document_date: Optional[str] = None,
        expiry_date: Optional[str] = None,
        certificate_code: Optional[str] = None,
    ) -> Document:
        document.title = title.strip()
        document.description = description.strip() if description else None
        document.category = category.strip() if category else None
        document.author = author.strip() if author else None

        if certificate_code is not None and certificate_code.strip():
            document.certificate_code = certificate_code.strip().upper()

        if tags is not None:
            tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
            document.tags = ", ".join(sorted(set(tag_list))) if tag_list else None

        if document_date:
            try:
                document.document_date = datetime.strptime(document_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            document.document_date = None

        if expiry_date:
            try:
                document.expiry_date = datetime.strptime(expiry_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            document.expiry_date = None

        document.updated_at = utc_now()
        db.session.commit()
        return document

    def replace_file(self, document: Document, new_file_storage) -> Document:
        orig_name, ext, mime_type, file_size, processed_bytes = self.storage.validate_and_process_upload(new_file_storage)
        new_stored_filename = self.storage.save_file(processed_bytes, ext)

        old_stored_filename = document.stored_filename

        # Update record
        document.stored_filename = new_stored_filename
        document.original_filename = orig_name
        document.file_extension = ext
        document.mime_type = mime_type
        document.file_size = file_size
        document.file_data = processed_bytes
        document.updated_at = utc_now()

        db.session.commit()

        # Safely remove old file after successful database commit
        self.storage.delete_file(old_stored_filename)

        return document

    def deactivate_document(self, document: Document) -> Document:
        document.is_active = False
        document.deleted_at = utc_now()
        db.session.commit()
        return document

    def reactivate_document(self, document: Document) -> Document:
        document.is_active = True
        document.deleted_at = None
        db.session.commit()
        return document

    def permanently_delete_document(self, document: Document) -> str:
        public_id = document.public_id
        stored_file = document.stored_filename

        # 1. Record in RetiredPublicId tombstone table so ID is never reused
        if not RetiredPublicId.query.filter_by(public_id=public_id).first():
            tombstone = RetiredPublicId(
                public_id=public_id,
                retired_at=utc_now(),
                reason="permanently_deleted"
            )
            db.session.add(tombstone)

        # 2. Delete document record
        db.session.delete(document)
        db.session.commit()

        # 3. Clean up physical files safely
        self.storage.delete_file(stored_file)
        self.qr.delete_qr(public_id)

        return public_id

    def lookup_public_document(self, identifier: str) -> Tuple[Optional[Document], str]:
        """
        Looks up a document for the public URL or verification by public_id,
        certificate_code (e.g. THX-SEP2626-093), or 4-digit code.
        """
        if not identifier:
            return None, "not_found"

        identifier = identifier.strip()

        # Check tombstone first
        if RetiredPublicId.query.filter_by(public_id=identifier).first():
            return None, "retired"

        # 1. Exact match on public_id
        doc = Document.query.filter_by(public_id=identifier).first()

        # 2. Match by certificate_code (exact or case-insensitive)
        if not doc:
            doc = Document.query.filter(Document.certificate_code.ilike(identifier)).first()

        # 3. Match by 4-digit code or numeric portion (e.g. '093', '2626', 'THX-XXXX')
        if not doc:
            clean_digits = "".join(c for c in identifier if c.isdigit())
            if len(clean_digits) >= 3:
                doc = Document.query.filter(
                    (Document.certificate_code.ilike(f"%{clean_digits}%")) |
                    (Document.public_id.ilike(f"%{clean_digits}%"))
                ).first()

        if not doc:
            return None, "not_found"

        if not doc.is_active:
            return doc, "inactive"

        return doc, "active"

    def log_scan(self, document: Document, user_agent: Optional[str]):
        """
        Logs a scan event. IP addresses are strictly omitted for privacy.
        """
        try:
            log_entry = ScanLog(
                document_id=document.id,
                scanned_at=utc_now(),
                user_agent=user_agent[:500] if user_agent else None
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def search_and_filter(
        self,
        query_str: Optional[str] = None,
        category: Optional[str] = None,
        file_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "newest",
        page: int = 1,
        per_page: int = 10,
    ):
        query = Document.query

        if query_str:
            term = f"%{query_str.strip()}%"
            query = query.filter(
                or_(
                    Document.title.ilike(term),
                    Document.public_id.ilike(term),
                    Document.description.ilike(term),
                    Document.author.ilike(term),
                    Document.tags.ilike(term),
                )
            )

        if category:
            query = query.filter(Document.category == category)

        if file_type:
            query = query.filter(Document.file_extension == file_type.lower())

        if status:
            if status == "active":
                query = query.filter(Document.is_active.is_(True))
            elif status == "inactive":
                query = query.filter(Document.is_active.is_(False))
            elif status == "expired":
                today = datetime.now().date()
                query = query.filter(Document.expiry_date.isnot(None), Document.expiry_date < today)

        if date_from:
            try:
                df = datetime.strptime(date_from.strip(), "%Y-%m-%d")
                query = query.filter(Document.uploaded_at >= df)
            except ValueError:
                pass

        if date_to:
            try:
                dt = datetime.strptime(date_to.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                query = query.filter(Document.uploaded_at <= dt)
            except ValueError:
                pass

        if sort_by == "oldest":
            query = query.order_by(asc(Document.uploaded_at))
        elif sort_by == "title":
            query = query.order_by(asc(Document.title))
        else:  # newest default
            query = query.order_by(desc(Document.uploaded_at))

        return query.paginate(page=page, per_page=per_page, error_out=False)
