import re
import urllib.parse
from flask import Flask, jsonify, request, Response

# Regex matching directory traversal attempts in decoded or raw form
TRAVERSAL_PATTERN = re.compile(r"(?:^|/)\.\.(?:/|$)|%2e%2e", re.IGNORECASE)

# File extensions that should never be served directly over HTTP
BLOCKED_EXTENSIONS = {
    ".py",
    ".pyc",
    ".pyo",
    ".pyd",
    ".yaml",
    ".yml",
    ".ini",
    ".env",
    ".cfg",
    ".conf",
    ".toml",
    ".md",
    ".sh",
    ".bash",
}

# Explicit filenames / patterns to block
BLOCKED_EXACT_NAMES = {
    "dockerfile",
    ".dockerignore",
    ".gitignore",
    "requirements.txt",
    "pytest.ini",
    "wsgi.py",
    "render.yaml",
    "render.yml",
    "spec.md",
    "problem_statement.md",
}

# Blocked directory segments
BLOCKED_DIR_SEGMENTS = {
    "__pycache__",
    "tests",
    "tools",
}


def is_sensitive_path(raw_url: str) -> bool:
    """Determine if a requested URL path targets sensitive files or directories."""
    # Check for null byte injections
    if "\x00" in raw_url:
        return True

    # Strip query string and fragment
    path = urllib.parse.urlsplit(raw_url).path

    # Check traversal in raw/encoded string
    if TRAVERSAL_PATTERN.search(path):
        return True

    # Decode path
    decoded_path = urllib.parse.unquote(path)
    if "\x00" in decoded_path:
        return True

    # Check traversal in decoded path
    if ".." in decoded_path.split("/") or TRAVERSAL_PATTERN.search(decoded_path):
        return True

    clean_path = decoded_path.strip("/")
    if not clean_path:
        return False

    segments = [s for s in clean_path.split("/") if s]

    # Block any segment starting with a dot (e.g. .env, .git, .gitignore, .vscode)
    for seg in segments:
        if seg.startswith("."):
            return True
        if seg.lower() in BLOCKED_DIR_SEGMENTS:
            return True

    target_name = segments[-1].lower()

    if target_name in BLOCKED_EXACT_NAMES:
        return True

    # Check extension
    for ext in BLOCKED_EXTENSIONS:
        if target_name.endswith(ext):
            return True

    return False


def init_security(app: Flask) -> None:
    """Attach security hooks to the Flask application."""

    @app.before_request
    def block_sensitive_requests():
        # Check raw request path as well as any raw URI from WSGI environment
        raw_uri = request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI") or request.path
        if is_sensitive_path(request.path) or is_sensitive_path(raw_uri):
            return jsonify(error="Forbidden: direct access to sensitive file or path is blocked"), 403

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "0")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'self' blob:; frame-src 'self' blob:;",
        )
        return response
