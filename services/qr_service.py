import os
import io
import qrcode
from qrcode.constants import ERROR_CORRECT_H

class QRService:
    def __init__(self, qr_folder: str):
        self.qr_folder = os.path.abspath(qr_folder)
        os.makedirs(self.qr_folder, exist_ok=True)

    def get_public_url(self, public_id: str, public_base_url: str) -> str:
        """
        Returns permanent canonical public URL for document.
        """
        base = public_base_url.rstrip("/")
        return f"{base}/document/{public_id}"

    def get_qr_filepath(self, public_id: str) -> str:
        safe_id = os.path.basename(public_id)
        path = os.path.abspath(os.path.join(self.qr_folder, f"{safe_id}.png"))
        if not path.startswith(self.qr_folder):
            raise ValueError("Invalid public_id path.")
        return path

    def create_qr_image_bytes(self, url: str) -> bytes:
        """
        Generates deterministic PNG bytes for the given URL.
        Uses Error Correction H, box size 10, border 4 modules.
        """
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to buffer
        buffer = io.BytesIO()
        # Ensure consistent PNG output
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def generate_and_save_qr(self, public_id: str, public_base_url: str) -> str:
        """
        Generates and saves the QR PNG for the given public_id.
        Returns the absolute filepath to the generated PNG.
        """
        target_path = self.get_qr_filepath(public_id)
        url = self.get_public_url(public_id, public_base_url)
        png_bytes = self.create_qr_image_bytes(url)

        with open(target_path, "wb") as f:
            f.write(png_bytes)

        return target_path

    def get_or_regenerate_qr(self, public_id: str, public_base_url: str) -> str:
        """
        Returns path to QR image, automatically regenerating it if missing or empty.
        """
        target_path = self.get_qr_filepath(public_id)
        if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
            return self.generate_and_save_qr(public_id, public_base_url)
        return target_path

    def delete_qr(self, public_id: str) -> bool:
        """
        Deletes the QR file if it exists.
        """
        try:
            target_path = self.get_qr_filepath(public_id)
            if os.path.exists(target_path):
                os.remove(target_path)
                return True
        except Exception:
            pass
        return False
