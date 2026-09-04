import pytest
from app.models import AnnotationSet
from app.renderer import render
from tests.pdf_probe import extract_placements, find
from tests.test_models import MINIMAL

DATA = {"taxpayer": {"firstName": "Ada"}}

def test_value_lands_inside_its_declared_box(f1040_path):
    aset = AnnotationSet.model_validate(MINIMAL)
    out = render(aset, DATA, f1040_path)
    p = find(extract_placements(out), "Ada")
    box = aset.annotations[0].box
    assert box.x <= p["x"] <= box.x + box.width
    assert box.y <= p["y"] <= box.y + box.height

def test_output_preserves_the_original_page_count(f1040_path):
    from pypdf import PdfReader; import io
    out = render(AnnotationSet.model_validate(MINIMAL), DATA, f1040_path)
    assert len(PdfReader(io.BytesIO(out)).pages) == 2

def test_absent_value_draws_nothing(f1040_path):
    out = render(AnnotationSet.model_validate(MINIMAL), {}, f1040_path)
    assert not [p for p in extract_placements(out) if p["text"].strip() == "Ada"]

def test_false_condition_suppresses_the_annotation(f1040_path):
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "condition": {"path": "$.filingStatus", "op": "equals", "value": "mfj"}}]}
    out = render(AnnotationSet.model_validate(doc), {**DATA, "filingStatus": "single"}, f1040_path)
    assert not [p for p in extract_placements(out) if "Ada" in p["text"]]

def test_overflow_shrink_reduces_size_but_never_below_minsize(f1040_path):
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "box": {"x": 40, "y": 96, "width": 30, "height": 14},
           "overflow": "shrink", "minSize": 6, "style": {"size": 12}}]}
    out = render(AnnotationSet.model_validate(doc),
                 {"taxpayer": {"firstName": "Bartholomew Fitzgerald"}}, f1040_path)
    p = find(extract_placements(out), "Bartholomew")
    assert 6 <= p["size"] < 12

def test_overflow_error_raises_naming_the_annotation(f1040_path):
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "box": {"x": 40, "y": 96, "width": 20, "height": 14}, "overflow": "error"}]}
    with pytest.raises(ValueError, match="first_name"):
        render(AnnotationSet.model_validate(doc),
               {"taxpayer": {"firstName": "Bartholomew Fitzgerald"}}, f1040_path)

def test_debug_mode_draws_more_than_normal_mode(f1040_path):
    aset = AnnotationSet.model_validate(MINIMAL)
    assert len(render(aset, DATA, f1040_path, debug=True)) > \
           len(render(aset, DATA, f1040_path))
