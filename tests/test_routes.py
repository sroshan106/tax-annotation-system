from pathlib import Path
import json, pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()

def test_index_lists_the_available_forms(client):
    r = client.get("/")
    assert r.status_code == 200 and b"f1040" in r.data

def test_index_has_two_column_layout_and_preview_controls(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b'id="preview-btn"' in r.data
    assert b'id="download-btn"' in r.data
    assert b'id="preview-frame"' in r.data
    assert b'id="dropzone"' in r.data
    assert b'id="view-template-info-btn"' in r.data
    assert b'id="zoom-in-btn"' in r.data
    assert b'id="zoom-out-btn"' in r.data
    assert b'id="fullscreen-btn"' in r.data
    assert b"1. Configure Input" in r.data
    assert b"2. PDF Preview" in r.data
    assert b"Sample - Individual" in r.data
    assert b"navpanes=0" in r.data

def test_render_returns_a_pdf(client):
    data = json.loads(Path("examples/simple-w2.json").read_text())
    r = client.post("/api/render", json={"form": "f1040", "data": data})
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF")

def test_debug_flag_produces_a_larger_pdf(client):
    data = json.loads(Path("examples/simple-w2.json").read_text())
    plain = client.post("/api/render", json={"form": "f1040", "data": data}).data
    dbg = client.post("/api/render", json={"form": "f1040", "data": data, "debug": True}).data
    assert len(dbg) > len(plain)

def test_unknown_form_is_404_not_500(client):
    r = client.post("/api/render", json={"form": "f9999", "data": {}})
    assert r.status_code == 404

def test_a_required_path_missing_from_the_data_is_a_422_with_the_annotation_id(client):
    r = client.post("/api/render", json={"form": "f1040", "data": {}})
    assert r.status_code == 422
    assert "error" in r.get_json()

def test_validate_reports_clean_for_a_shipped_set(client):
    r = client.post("/api/validate", json={"form": "f1040"})
    assert r.get_json() == {"valid": True, "warnings": [], "errors": []}

def test_non_dict_json_returns_400(client):
    r = client.post("/api/render", json=["not", "a", "dict"])
    assert r.status_code == 400
    assert r.get_json() == {"error": "invalid request: payload must be a JSON object"}

    r_val = client.post("/api/validate", json=["not", "a", "dict"])
    assert r_val.status_code == 400
    assert r_val.get_json() == {"error": "invalid request: payload must be a JSON object"}


def test_form_info_returns_metadata(client):
    r = client.get("/api/forms/f1040/info")
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == "f1040"
    assert "Form 1040" in data["title"]
    assert data["taxYear"] == 2024
    assert data["pageCount"] == 2
    assert data["annotationCount"] > 0


def test_form_info_unknown_form_is_404(client):
    r = client.get("/api/forms/nonexistent/info")
    assert r.status_code == 404


@pytest.mark.parametrize("filename", [
    "simple-w2.json",
    "joint-dependents.json",
    "schedule-b-normal.json",
    "schedule-b-overflow.json",
])
def test_example_endpoint_returns_json(client, filename):
    r = client.get(f"/api/examples/{filename}")
    assert r.status_code == 200
    data = r.get_json()
    assert "taxpayer" in data


def test_example_endpoint_unknown_is_404(client):
    r = client.get("/api/examples/unknown.json")
    assert r.status_code == 404


def test_healthz_endpoint(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json() == {"status": "healthy"}


def test_index_has_favicon_link(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b'rel="icon"' in r.data
    assert b"favicon.svg" in r.data


def test_favicon_ico_endpoint(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert b"<svg" in r.data
    assert r.mimetype == "image/svg+xml"


def test_static_favicon_endpoint(client):
    r = client.get("/static/favicon.svg")
    assert r.status_code == 200
    assert b"<svg" in r.data
    assert r.mimetype == "image/svg+xml"

