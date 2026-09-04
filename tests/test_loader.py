import json, pytest
from app.loader import load_set, verify_source, SourceMismatch
from tests.test_models import MINIMAL

def _write(tmp_path, doc):
    p = tmp_path / "set.json"
    p.write_text(json.dumps(doc))
    return p

def test_load_returns_a_validated_set(tmp_path):
    assert load_set(_write(tmp_path, MINIMAL)).form.id == "f1040"

def test_invalid_set_raises_with_the_offending_field(tmp_path):
    bad = {**MINIMAL, "source": {**MINIMAL["source"], "sha256": "nope"}}
    with pytest.raises(ValueError, match="sha256"):
        load_set(_write(tmp_path, bad))

def test_sha_mismatch_warns_by_default(tmp_path, f1040_path):
    aset = load_set(_write(tmp_path, MINIMAL))
    warnings = verify_source(aset, f1040_path, strict=False)
    assert any("sha256" in w for w in warnings)

def test_sha_mismatch_raises_under_strict(tmp_path, f1040_path):
    aset = load_set(_write(tmp_path, MINIMAL))
    with pytest.raises(SourceMismatch):
        verify_source(aset, f1040_path, strict=True)

def test_page_count_mismatch_warns(tmp_path, f1040sb_path):
    aset = load_set(_write(tmp_path, MINIMAL))
    assert any("page count" in w for w in verify_source(aset, f1040sb_path, strict=False))
