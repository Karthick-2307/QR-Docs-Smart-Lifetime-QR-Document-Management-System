import re
from urllib.parse import urlparse, parse_qs
from flask import Blueprint, render_template, request, jsonify, current_app

scanner_bp = Blueprint("scanner", __name__)

UUID_REGEX = re.compile(
    r"^/document/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)
CERT_REGEX = re.compile(
    r"^/document/([A-Za-z0-9\-_]{3,50})$",
    re.IGNORECASE,
)

def validate_scanned_qr_url(scanned_url: str, public_base_url: str):
    """
    Validates that scanned_url matches public_base_url scheme & host,
    and points to a valid /document/<uuid4_or_cert_code> path or /?verifyId=...
    Returns (is_valid, public_id or None, error_message or None).
    """
    if not scanned_url or not isinstance(scanned_url, str):
        return False, None, "No URL provided."

    scanned_url = scanned_url.strip()
    parsed_base = urlparse(public_base_url)
    parsed_target = urlparse(scanned_url)

    # If target is full URL, scheme and netloc (hostname + port) must match base URL
    if parsed_target.scheme or parsed_target.netloc:
        # Check scheme
        if parsed_target.scheme.lower() != parsed_base.scheme.lower():
            return False, None, f"Scheme mismatch: expected '{parsed_base.scheme}', got '{parsed_target.scheme}'."

        # Check hostname and port
        target_netloc = parsed_target.netloc.lower()
        base_netloc = parsed_base.netloc.lower()

        if target_netloc != base_netloc:
            return False, None, f"Untrusted domain/host '{parsed_target.netloc}'. Must match system base URL."

    # Check for query param ?verifyId=...
    if parsed_target.query:
        qs = parse_qs(parsed_target.query)
        v_id = qs.get("verifyId", [None])[0] or qs.get("verify_id", [None])[0]
        if v_id and re.match(r"^[A-Za-z0-9\-_]{3,50}$", v_id.strip()):
            return True, v_id.strip(), None

    # Validate path matches /document/<uuid> or /document/<cert_code>
    match = UUID_REGEX.match(parsed_target.path)
    if match:
        public_id = match.group(1).lower()
        return True, public_id, None

    cert_match = CERT_REGEX.match(parsed_target.path)
    if cert_match:
        public_id = cert_match.group(1)
        return True, public_id, None

    return False, None, "Invalid URL path. Expected format: /document/<uuid>"

@scanner_bp.route("/scanner")
def scanner_page():
    return render_template(
        "scanner/scanner.html",
        public_base_url=current_app.config["PUBLIC_BASE_URL"]
    )

@scanner_bp.route("/scanner/validate-url", methods=["POST"])
def validate_url():
    data = request.get_json(silent=True) or {}
    scanned_url = data.get("url")

    is_valid, public_id, error = validate_scanned_qr_url(
        scanned_url,
        current_app.config["PUBLIC_BASE_URL"]
    )

    if not is_valid:
        return jsonify({
            "valid": False,
            "error": error or "The scanned QR code is not a valid document URL for this system."
        }), 400

    return jsonify({
        "valid": True,
        "public_id": public_id,
        "redirect_url": f"/document/{public_id}"
    })

