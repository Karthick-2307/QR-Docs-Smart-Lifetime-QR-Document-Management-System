import io
import os
from models import Document
from services import get_qr_service

def test_qr_generation_and_url_correctness(auth_client, sample_pdf_bytes, app):
    auth_client.post(
        "/admin/upload",
        data={
            "title": "QR Integrity Test",
            "file": (io.BytesIO(sample_pdf_bytes), "integrity.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="QR Integrity Test").first()
        pub_id = doc.public_id
        qr_service = get_qr_service()

        expected_url = f"{app.config['PUBLIC_BASE_URL']}/document/{pub_id}"
        actual_url = qr_service.get_public_url(pub_id, app.config["PUBLIC_BASE_URL"])
        assert actual_url == expected_url

        qr_path = qr_service.get_qr_filepath(pub_id)
        assert os.path.exists(qr_path)
        assert os.path.getsize(qr_path) > 0

def test_qr_png_byte_identical_across_operations(auth_client, sample_pdf_bytes, sample_png_bytes, app):
    """
    CRITICAL CORE RULE TEST:
    Verifies that the QR code PNG bytes remain 100% byte-identical
    after:
    1. Metadata edit
    2. File replacement
    3. Deactivation and Reactivation
    4. Deletion of the PNG file on disk and subsequent automatic regeneration
    """
    # 1. Upload initial document
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Original Document",
            "description": "Original description",
            "category": "Cat1",
            "tags": "tag1",
            "file": (io.BytesIO(sample_pdf_bytes), "orig.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="Original Document").first()
        pub_id = doc.public_id
        qr_service = get_qr_service()
        qr_path = qr_service.get_qr_filepath(pub_id)

        with open(qr_path, "rb") as f:
            initial_png_bytes = f.read()

        assert len(initial_png_bytes) > 0

    # 2. Edit metadata
    auth_client.post(
        f"/admin/document/{pub_id}/edit",
        data={
            "title": "Updated Title After Edit",
            "description": "Completely new description",
            "category": "NewCategory",
            "tags": "newtag, updated",
            "author": "New Author",
            "document_date": "2026-10-30",
            "expiry_date": "2028-12-31",
        },
        follow_redirects=True,
    )

    with open(qr_path, "rb") as f:
        bytes_after_metadata_edit = f.read()
    assert bytes_after_metadata_edit == initial_png_bytes, "QR changed after metadata edit!"

    # 3. Replace the physical file with a PNG image
    auth_client.post(
        f"/admin/document/{pub_id}/replace-file",
        data={
            "file": (io.BytesIO(sample_png_bytes), "replaced.png"),
        },
        follow_redirects=True,
    )

    with open(qr_path, "rb") as f:
        bytes_after_file_replace = f.read()
    assert bytes_after_file_replace == initial_png_bytes, "QR changed after file replacement!"

    # 4. Deactivate and Reactivate
    auth_client.post(f"/admin/document/{pub_id}/deactivate", follow_redirects=True)
    auth_client.post(f"/admin/document/{pub_id}/reactivate", follow_redirects=True)

    with open(qr_path, "rb") as f:
        bytes_after_lifecycle = f.read()
    assert bytes_after_lifecycle == initial_png_bytes, "QR changed after deactivate/reactivate!"

    # 5. Delete the PNG file from disk and regenerate
    os.remove(qr_path)
    assert not os.path.exists(qr_path)

    with app.app_context():
        regenerated_path = qr_service.get_or_regenerate_qr(pub_id, app.config["PUBLIC_BASE_URL"])
        assert os.path.exists(regenerated_path)

        with open(regenerated_path, "rb") as f:
            regenerated_bytes = f.read()

    assert regenerated_bytes == initial_png_bytes, "Regenerated QR does not match initial PNG bytes!"

def test_admin_download_qr_route(auth_client, sample_pdf_bytes, app):
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Download QR Test",
            "file": (io.BytesIO(sample_pdf_bytes), "doc.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="Download QR Test").first()
        pub_id = doc.public_id

    # Admin route serves image/png
    res = auth_client.get(f"/qr/{pub_id}.png")
    assert res.status_code == 200
    assert res.mimetype == "image/png"
    assert res.data.startswith(b"\x89PNG\r\n\x1a\n")

def test_regenerate_all_qr_action(auth_client, sample_pdf_bytes, app):
    # Upload 2 documents
    auth_client.post(
        "/admin/upload",
        data={"title": "Doc 1", "file": (io.BytesIO(sample_pdf_bytes), "doc1.pdf")},
        follow_redirects=True,
    )
    auth_client.post(
        "/admin/upload",
        data={"title": "Doc 2", "file": (io.BytesIO(sample_pdf_bytes), "doc2.pdf")},
        follow_redirects=True,
    )

    res = auth_client.post("/admin/settings/regenerate-all-qr", follow_redirects=True)
    assert res.status_code == 200
    assert b"Successfully regenerated" in res.data

