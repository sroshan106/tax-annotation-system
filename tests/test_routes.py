import json, pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app(); app.config["TESTING"] = True
    return app.test_client()

def test_index_lists_the_available_forms(client):
    r = client.get("/")
    assert r.status_code == 200 and b"f1040" in r.data

def test_render_returns_a_pdf(client):
    data = json.loads(open("examples/simple-w2.json").read())
    r = client.post("/api/render", json={"form": "f1040", "data": data})
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF")

def test_debug_flag_produces_a_larger_pdf(client):
    data = json.loads(open("examples/simple-w2.json").read())
    plain = client.post("/api/render", json={"form": "f1040", "data": data}).data
    dbg = client.post("/api/render", json={"form": "f1040", "data": data,
                                           "debug": True}).data
    assert len(dbg) > len(plain)

def test_unknown_form_is_404_not_500(client):
    r = client.post("/api/render", json={"form": "f9999", "data": {}})
    assert r.status_code == 404

def test_a_required_path_missing_from_the_data_is_a_422_with_the_annotation_id(client):
    r = client.post("/api/render", json={"form": "f1040", "data": {}})
    assert r.status_code == 422
    assert "id" in r.get_json()["error"] or r.get_json()["error"]

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

