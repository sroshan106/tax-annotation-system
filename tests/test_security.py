import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()

@pytest.mark.parametrize("path", [
    "/.env",
    "/.env.production",
    "/.env.local",
    "/.git",
    "/.git/config",
    "/.git/HEAD",
    "/.gitignore",
    "/.dockerignore",
    "/.vscode/settings.json",
    "/.bash_history",
])
def test_blocks_hidden_files_and_directories(client, path):
    r = client.get(path)
    assert r.status_code == 403
    data = r.get_json()
    assert data is not None
    assert "Forbidden" in data.get("error", "")

@pytest.mark.parametrize("path", [
    "/render.yaml",
    "/Dockerfile",
    "/requirements.txt",
    "/pytest.ini",
    "/SPEC.md",
    "/problem_statement.md",
])
def test_blocks_infrastructure_and_config_files(client, path):
    r = client.get(path)
    assert r.status_code == 403
    data = r.get_json()
    assert data is not None
    assert "Forbidden" in data.get("error", "")

@pytest.mark.parametrize("path", [
    "/wsgi.py",
    "/app/routes.py",
    "/app/models.py",
    "/tests/test_security.py",
    "/app/__pycache__/routes.cpython-312.pyc",
])
def test_blocks_source_code_and_python_files(client, path):
    r = client.get(path)
    assert r.status_code == 403
    data = r.get_json()
    assert data is not None
    assert "Forbidden" in data.get("error", "")

@pytest.mark.parametrize("path", [
    "/static/../render.yaml",
    "/static/../../.env",
    "/static/..%2f.env",
    "/%2e%2e/render.yaml",
    "/%2e%2e/%2e%2e/etc/passwd",
])
def test_blocks_path_traversal_attempts(client, path):
    r = client.get(path)
    assert r.status_code == 403
    data = r.get_json()
    assert data is not None
    assert "Forbidden" in data.get("error", "")

@pytest.mark.parametrize("path", [
    "/",
    "/healthz",
    "/favicon.ico",
    "/api/forms/f1040/info",
    "/api/examples/joint-dependents.json",
])
def test_security_headers_present_on_responses(client, path):
    r = client.get(path)
    assert r.status_code in (200, 304)
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") in ("SAMEORIGIN", "DENY")
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in r.headers


def test_query_parameters_do_not_trigger_false_positives(client):
    r = client.get("/api/forms/f1040/info?ref=test.py&note=render.yaml")
    assert r.status_code == 200
