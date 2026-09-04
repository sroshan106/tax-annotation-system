import pytest
from pydantic import ValidationError
from app.models import AnnotationSet, FieldAnnotation, Box

MINIMAL = {
    "specVersion": "1.0",
    "form": {"id": "f1040", "title": "U.S. Individual Income Tax Return",
             "taxYear": 2024, "revision": "2024", "jurisdiction": "US-IRS"},
    "source": {"url": "https://www.irs.gov/pub/irs-pdf/f1040.pdf",
               "sha256": "0" * 64, "pageCount": 2},
    "pages": [{"number": 1, "width": 612, "height": 792},
              {"number": 2, "width": 612, "height": 792}],
    "annotations": [{
        "kind": "field", "id": "first_name", "label": "First name",
        "page": 1, "box": {"x": 40, "y": 96, "width": 200, "height": 14},
        "type": "text", "value": "$.taxpayer.firstName",
    }],
}

def test_minimal_set_validates():
    s = AnnotationSet.model_validate(MINIMAL)
    assert isinstance(s.annotations[0], FieldAnnotation)
    assert s.annotations[0].box == Box(x=40, y=96, width=200, height=14)

def test_kind_discriminates_field_from_group():
    doc = {**MINIMAL, "annotations": [{
        "kind": "group", "id": "sch_b_payers", "label": "Payers",
        "page": 1, "source": "$.income.interest[*]",
        "rowHeight": 16, "maxRows": 14,
        "firstRowBox": {"x": 40, "y": 200, "width": 400, "height": 14},
        "overflowStrategy": "statement", "overflowTarget": "first_name",
        "columns": [{"kind": "field", "id": "payer", "label": "Payer",
                     "page": 1, "box": {"x": 0, "y": 0, "width": 300, "height": 14},
                     "type": "text", "value": "$.name"}],
    }]}
    s = AnnotationSet.model_validate(doc)
    assert s.annotations[0].kind == "group"

def test_non_base14_font_requires_fallback():
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "style": {"font": "Comic Sans MS", "size": 9}}]}
    with pytest.raises(ValidationError, match="fontFallback"):
        AnnotationSet.model_validate(doc)

def test_page_reference_must_exist():
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0], "page": 7}]}
    with pytest.raises(ValidationError, match="page 7"):
        AnnotationSet.model_validate(doc)

def test_ids_must_be_unique():
    a = MINIMAL["annotations"][0]
    doc = {**MINIMAL, "annotations": [a, dict(a)]}
    with pytest.raises(ValidationError, match="duplicate"):
        AnnotationSet.model_validate(doc)

def test_generated_schema_is_current():
    """Fails if someone edits models.py and forgets to regenerate."""
    import os, pathlib, subprocess, sys
    p = pathlib.Path("schema/annotation-set.schema.json")
    before = p.read_text()
    subprocess.run([sys.executable, "tools/gen_schema.py"], check=True,
                   env={**os.environ, "PYTHONPATH": "."})
    assert p.read_text() == before, "run: python tools/gen_schema.py"
