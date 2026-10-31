import os
import io
import shutil
import pytest
from PIL import Image

from app import create_app
from config import TestConfig
from extensions import db
from models import Admin

@pytest.fixture(scope="session")
def sample_pdf_bytes():
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

@pytest.fixture(scope="session")
def sample_png_bytes():
    img = Image.new("RGB", (20, 20), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture(scope="session")
def sample_jpeg_bytes():
    img = Image.new("RGB", (20, 20), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.fixture
def app():
    # Setup test directories
    test_upload = os.path.join(TestConfig.BASE_DIR, "instance", "test_uploads")
    test_qr = os.path.join(TestConfig.BASE_DIR, "instance", "test_qr")
    os.makedirs(test_upload, exist_ok=True)
    os.makedirs(test_qr, exist_ok=True)

    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        admin = Admin(username="testadmin")
        admin.set_password("SecretPass123!")
        db.session.add(admin)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()

    # Cleanup folders
    shutil.rmtree(test_upload, ignore_errors=True)
    shutil.rmtree(test_qr, ignore_errors=True)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client):
    client.post(
        "/login",
        data={"username": "testadmin", "password": "SecretPass123!"},
        follow_redirects=True,
    )
    return client

