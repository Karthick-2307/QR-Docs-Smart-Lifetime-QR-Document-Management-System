import os
import uuid
import io
from typing import Tuple
from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

class StorageValidationError(Exception):
    pass

class StorageService:
    def __init__(self, upload_folder: str, max_size_bytes: int = 10 * 1024 * 1024):
        self.upload_folder = os.path.abspath(upload_folder)
        self.max_size_bytes = max_size_bytes
        os.makedirs(self.upload_folder, exist_ok=True)

        self.allowed_extensions = {"pdf", "png", "jpg", "jpeg"}
        self.mime_types = {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }

    def _validate_magic_bytes(self, content_prefix: bytes, extension: str) -> bool:
        if extension == "pdf":
            return content_prefix.startswith(b"%PDF-")
        elif extension == "png":
            return content_prefix.startswith(b"\x89PNG\r\n\x1a\n")
        elif extension in ("jpg", "jpeg"):
            return content_prefix.startswith(b"\xff\xd8\xff")
        return False

    def validate_and_process_upload(self, file_storage: FileStorage) -> Tuple[str, str, str, int, bytes]:
        """
        Validates file storage object, inspects magic bytes, sanitizes image EXIF,
        and returns:
            (original_filename, extension, mime_type, file_size, processed_bytes)
        """
        if not file_storage or not file_storage.filename:
            raise StorageValidationError("No file was selected for upload.")

        original_filename = secure_filename(file_storage.filename)
        if not original_filename:
            original_filename = "document"

        # Check extension
        parts = original_filename.rsplit(".", 1)
        if len(parts) < 2:
            raise StorageValidationError("Uploaded file has no extension.")
        
        ext = parts[1].lower()
        if ext not in self.allowed_extensions:
            raise StorageValidationError(
                f"File extension '.{ext}' is not permitted. Allowed: {', '.join(sorted(self.allowed_extensions))}"
            )

        # Read content to validate size and headers
        file_storage.seek(0, os.SEEK_END)
        file_size = file_storage.tell()
        file_storage.seek(0)

        if file_size <= 0:
            raise StorageValidationError("Uploaded file is empty (0 bytes).")
        if file_size > self.max_size_bytes:
            raise StorageValidationError(
                f"File size ({file_size / (1024*1024):.2f} MB) exceeds maximum allowed limit ({self.max_size_bytes / (1024*1024):.2f} MB)."
            )

        content = file_storage.read()
        file_storage.seek(0)

        # Magic bytes check
        if not self._validate_magic_bytes(content[:16], ext):
            raise StorageValidationError(
                f"File signature mismatch. The file content does not match extension '.{ext}'."
            )

        mime_type = self.mime_types[ext]
        processed_bytes = content

        # Image verification and EXIF sanitization
        if ext in ("png", "jpg", "jpeg"):
            try:
                img_io = io.BytesIO(content)
                with Image.open(img_io) as img:
                    img.verify()

                # Re-open to process and strip metadata
                img_io.seek(0)
                with Image.open(img_io) as img:
                    # Strip EXIF / metadata by creating clean image buffer
                    clean_io = io.BytesIO()
                    img_format = "PNG" if ext == "png" else "JPEG"
                    
                    if img_format == "JPEG" and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # Saving without copying info/exif strips metadata
                    img.save(clean_io, format=img_format, quality=95)
                    processed_bytes = clean_io.getvalue()
                    file_size = len(processed_bytes)
            except Exception as e:
                raise StorageValidationError(f"Invalid or corrupted image file: {str(e)}")

        return original_filename, ext, mime_type, file_size, processed_bytes

    def save_file(self, processed_bytes: bytes, extension: str) -> str:
        """
        Saves bytes with a randomized UUID filename inside upload_folder.
        Returns stored_filename.
        """
        stored_filename = f"{uuid.uuid4().hex}.{extension}"
        target_path = os.path.join(self.upload_folder, stored_filename)

        # Prevent directory traversal
        target_path = os.path.abspath(target_path)
        if not target_path.startswith(self.upload_folder):
            raise StorageValidationError("Security violation: invalid file destination path.")

        with open(target_path, "wb") as f:
            f.write(processed_bytes)

        return stored_filename

    def get_file_path(self, stored_filename: str) -> str:
        """
        Returns absolute path of stored file, verifying it resides in upload_folder.
        """
        safe_name = os.path.basename(stored_filename)
        path = os.path.abspath(os.path.join(self.upload_folder, safe_name))
        if not path.startswith(self.upload_folder):
            raise StorageValidationError("Access denied: path traversal attempt detected.")
        return path

    def delete_file(self, stored_filename: str) -> bool:
        """
        Safely deletes a stored file.
        """
        try:
            path = self.get_file_path(stored_filename)
            if os.path.exists(path):
                os.remove(path)
                return True
        except Exception:
            pass
        return False
