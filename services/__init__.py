from flask import current_app
from services.storage_service import StorageService, StorageValidationError
from services.qr_service import QRService
from services.document_service import DocumentService

def get_storage_service() -> StorageService:
    if not hasattr(current_app, "storage_service"):
        current_app.storage_service = StorageService(
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            max_size_bytes=current_app.config["MAX_UPLOAD_SIZE"],
        )
    return current_app.storage_service

def get_qr_service() -> QRService:
    if not hasattr(current_app, "qr_service"):
        current_app.qr_service = QRService(
            qr_folder=current_app.config["QR_FOLDER"]
        )
    return current_app.qr_service

def get_document_service() -> DocumentService:
    if not hasattr(current_app, "document_service"):
        storage = get_storage_service()
        qr = get_qr_service()
        current_app.document_service = DocumentService(storage, qr)
    return current_app.document_service

