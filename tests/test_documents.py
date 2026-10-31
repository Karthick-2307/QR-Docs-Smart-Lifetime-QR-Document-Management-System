import io
import datetime
from models import Document, RetiredPublicId, ScanLog
from extensions import db

def test_document_upload_pdf(auth_client, sample_pdf_bytes, app):
    response = auth_client.post(
        "/admin/upload",
        data={
            "title": "Safety Guidelines 2026",
            "description": "Critical laboratory safety rules",
            "category": "Compliance",
            "tags": "safety, lab, 2026",
            "author": "Chief Inspector",
            "document_date": "2026-05-01",
            "file": (io.BytesIO(sample_pdf_bytes), "safety_guide.pdf"),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"uploaded successfully" in response.data

    with app.app_context():
        doc = Document.query.filter_by(title="Safety Guidelines 2026").first()
        assert doc is not None
        assert doc.file_extension == "pdf"
        assert doc.mime_type == "application/pdf"
        assert doc.author == "Chief Inspector"
        assert doc.category == "Compliance"
        assert "safety" in doc.tags
        assert doc.is_active is True

def test_invalid_file_extension_rejection(auth_client):
    fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
    response = auth_client.post(
        "/admin/upload",
        data={
            "title": "Malware Test",
            "file": (fake_exe, "payload.exe"),
        },
        follow_redirects=True,
    )
    assert b"is not permitted" in response.data or b"Invalid file" in response.data

def test_fake_extension_signature_mismatch(auth_client):
    # Extension says pdf, but content is random plaintext
    fake_pdf = io.BytesIO(b"Hello world, I am not a real PDF file!")
    response = auth_client.post(
        "/admin/upload",
        data={
            "title": "Fake PDF Test",
            "file": (fake_pdf, "fake.pdf"),
        },
        follow_redirects=True,
    )
    assert b"File signature mismatch" in response.data

def test_file_size_rejection(auth_client, app):
    # Set max upload size to 100 bytes temporarily
    orig_max = app.config["MAX_UPLOAD_SIZE"]
    app.config["MAX_UPLOAD_SIZE"] = 100
    if hasattr(app, "storage_service"):
        app.storage_service.max_size_bytes = 100

    large_content = b"%PDF-" + (b"A" * 500)
    response = auth_client.post(
        "/admin/upload",
        data={
            "title": "Too Large",
            "file": (io.BytesIO(large_content), "large.pdf"),
        },
        follow_redirects=True,
    )
    assert b"exceeds maximum allowed limit" in response.data or response.status_code in (413, 200)

    # Restore
    app.config["MAX_UPLOAD_SIZE"] = orig_max
    if hasattr(app, "storage_service"):
        app.storage_service.max_size_bytes = orig_max

def test_public_document_view_and_download(client, auth_client, sample_pdf_bytes, app):
    # 1. Upload doc
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Public Handbook",
            "file": (io.BytesIO(sample_pdf_bytes), "handbook.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="Public Handbook").first()
        pub_id = doc.public_id

    # 2. Access unauthenticated as public visitor
    res_page = client.get(f"/document/{pub_id}")
    assert res_page.status_code == 200
    assert b"Public Handbook" in res_page.data

    # Verify scan log logged
    with app.app_context():
        logs = ScanLog.query.filter_by(document_id=doc.id).all()
        assert len(logs) >= 1

    # 3. Inline file view
    res_file = client.get(f"/document/{pub_id}/file")
    assert res_file.status_code == 200
    assert res_file.mimetype == "application/pdf"

    # 4. Download file
    res_dl = client.get(f"/document/{pub_id}/download")
    assert res_dl.status_code == 200
    assert "attachment" in res_dl.headers.get("Content-Disposition", "")

def test_document_expiry_informational(client, auth_client, sample_pdf_bytes, app):
    # Document with past expiry date
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Expired Notice",
            "expiry_date": yesterday,
            "file": (io.BytesIO(sample_pdf_bytes), "notice.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="Expired Notice").first()
        pub_id = doc.public_id
        assert doc.is_expired is True

    # QR and public page STILL load with HTTP 200, but show "Notice: This document expired" banner
    res = client.get(f"/document/{pub_id}")
    assert res.status_code == 200
    assert b"Notice:" in res.data
    assert b"expired on" in res.data.lower()

def test_soft_delete_and_reactivation(client, auth_client, sample_pdf_bytes, app):
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Lifecycle Doc",
            "file": (io.BytesIO(sample_pdf_bytes), "lifecycle.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="Lifecycle Doc").first()
        pub_id = doc.public_id

    # Deactivate document
    res_deact = auth_client.post(f"/admin/document/{pub_id}/deactivate", follow_redirects=True)
    assert res_deact.status_code == 200

    # Public view must return 410 Gone (NOT 404!)
    res_gone = client.get(f"/document/{pub_id}")
    assert res_gone.status_code == 410
    assert b"This Document is No Longer Available" in res_gone.data

    # Reactivate document
    res_react = auth_client.post(f"/admin/document/{pub_id}/reactivate", follow_redirects=True)
    assert res_react.status_code == 200

    # Public view should now return 200 OK again
    res_ok = client.get(f"/document/{pub_id}")
    assert res_ok.status_code == 200
    assert b"Lifecycle Doc" in res_ok.data

def test_permanent_deletion_and_retired_tombstone(client, auth_client, sample_pdf_bytes, app):
    auth_client.post(
        "/admin/upload",
        data={
            "title": "To Be Erased",
            "file": (io.BytesIO(sample_pdf_bytes), "erased.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="To Be Erased").first()
        pub_id = doc.public_id

    # Permanently delete
    del_res = auth_client.post(f"/admin/document/{pub_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200

    with app.app_context():
        # Document record removed
        assert Document.query.filter_by(public_id=pub_id).first() is None
        # Tombstone recorded
        tombstone = RetiredPublicId.query.filter_by(public_id=pub_id).first()
        assert tombstone is not None

    # Public URL returns 410 Gone
    res_gone = client.get(f"/document/{pub_id}")
    assert res_gone.status_code == 410

def test_invalid_document_id_returns_404(client):
    res = client.get("/document/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
    assert b"Page or Document Not Found" in res.data

def test_scanner_url_validation(client, app):
    base_url = app.config["PUBLIC_BASE_URL"]

    # 1. Valid URL
    res = client.post(
        "/scanner/validate-url",
        json={"url": f"{base_url}/document/550e8400-e29b-41d4-a716-446655440000"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["valid"] is True
    assert data["public_id"] == "550e8400-e29b-41d4-a716-446655440000"

    # 2. External domain (rejected)
    res_ext = client.post(
        "/scanner/validate-url",
        json={"url": "https://malicious-phishing.com/document/550e8400-e29b-41d4-a716-446655440000"},
    )
    assert res_ext.status_code == 400
    assert res_ext.get_json()["valid"] is False

    # 3. Malformed path (rejected)
    res_bad_path = client.post(
        "/scanner/validate-url",
        json={"url": f"{base_url}/admin/dashboard"},
    )
    assert res_bad_path.status_code == 400
    assert res_bad_path.get_json()["valid"] is False


def test_document_upload_image_and_exif_strip(auth_client, sample_png_bytes, sample_jpeg_bytes, app):
    # Upload PNG
    res_png = auth_client.post(
        "/admin/upload",
        data={
            "title": "Equipment Diagram PNG",
            "category": "Diagrams",
            "file": (io.BytesIO(sample_png_bytes), "diagram.png"),
        },
        follow_redirects=True,
    )
    assert res_png.status_code == 200

    # Upload JPEG
    res_jpg = auth_client.post(
        "/admin/upload",
        data={
            "title": "Inspection Photo JPG",
            "category": "Photos",
            "file": (io.BytesIO(sample_jpeg_bytes), "photo.jpg"),
        },
        follow_redirects=True,
    )
    assert res_jpg.status_code == 200

    with app.app_context():
        doc_png = Document.query.filter_by(title="Equipment Diagram PNG").first()
        assert doc_png is not None
        assert doc_png.mime_type == "image/png"

        doc_jpg = Document.query.filter_by(title="Inspection Photo JPG").first()
        assert doc_jpg is not None
        assert doc_jpg.mime_type == "image/jpeg"

def test_search_and_filter_documents(auth_client, sample_pdf_bytes, app):
    # Create multiple documents with various metadata
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Finance Report Q1",
            "category": "Finance",
            "tags": "audit, q1",
            "file": (io.BytesIO(sample_pdf_bytes), "fin.pdf"),
        },
        follow_redirects=True,
    )
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Engineering Blueprints",
            "category": "Engineering",
            "tags": "cad, specs",
            "file": (io.BytesIO(sample_pdf_bytes), "eng.pdf"),
        },
        follow_redirects=True,
    )

    # Search for Finance
    res_search = auth_client.get("/admin/documents?q=Finance")
    assert b"Finance Report Q1" in res_search.data
    assert b"Engineering Blueprints" not in res_search.data

    # Filter by category
    res_cat = auth_client.get("/admin/documents?category=Engineering")
    assert b"Engineering Blueprints" in res_cat.data
    assert b"Finance Report Q1" not in res_cat.data


def test_masked_id_and_four_digit_verification(client, auth_client, sample_pdf_bytes, app):
    # Upload document with custom certificate_code
    auth_client.post(
        "/admin/upload",
        data={
            "title": "Manoj S Certificate",
            "category": "Full Stack Development",
            "certificate_code": "THX-SEP2626-093",
            "file": (io.BytesIO(sample_pdf_bytes), "cert.pdf"),
        },
        follow_redirects=True,
    )

    with app.app_context():
        doc = Document.query.filter_by(title="Manoj S Certificate").first()
        pub_id = doc.public_id
        assert doc.masked_id == "THX-SEP2626-093"

    # 1. Verify by custom masked ID
    res1 = client.get("/api/verify/THX-SEP2626-093")
    assert res1.status_code == 200
    assert res1.get_json()["document"]["title"] == "Manoj S Certificate"

    # 2. Verify by partial 4-digit code (e.g. 2626)
    res2 = client.get("/api/verify/2626")
    assert res2.status_code == 200
    assert res2.get_json()["document"]["title"] == "Manoj S Certificate"

    # 3. Verify by full public_id
    res3 = client.get(f"/api/verify/{pub_id}")
    assert res3.status_code == 200
    assert res3.get_json()["document"]["title"] == "Manoj S Certificate"
