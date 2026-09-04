import pytest
from app.models import AnnotationSet
from app.renderer import render
from tests.pdf_probe import extract_placements, find
from tests.test_models import MINIMAL

def group_doc(max_rows=2, strategy="statement", target="sch_b_note"):
    ann = {"kind": "group", "id": "payers", "label": "Payers", "page": 1,
           "source": "$.income.interest[*]", "rowHeight": 16, "maxRows": max_rows,
           "firstRowBox": {"x": 40, "y": 300, "width": 400, "height": 14},
           "overflowStrategy": strategy,
           "columns": [
               {"kind": "field", "id": "payer", "label": "Payer", "page": 1,
                "box": {"x": 40, "y": 300, "width": 280, "height": 14},
                "type": "text", "value": "$.name"},
               {"kind": "field", "id": "amount", "label": "Amount", "page": 1,
                "box": {"x": 330, "y": 300, "width": 110, "height": 14},
                "type": "currency", "value": "$.amount",
                "style": {"align": "right"}}]}
    if strategy == "statement":
        ann["overflowTarget"] = target
    note = {"kind": "field", "id": target or "sch_b_note", "label": "Note", "page": 1,
            "box": {"x": 40, "y": 500, "width": 400, "height": 14},
            "type": "text", "value": "$.overflowNote"}
    return {**MINIMAL, "annotations": [ann, note]}

def data(n):
    return {"income": {"interest": [{"name": f"Bank {i}", "amount": 100.0 + i}
                                    for i in range(n)]},
            "overflowNote": "See attached statement"}

def test_each_row_is_offset_by_exactly_rowheight(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc()), data(2), f1040_path)
    pl = extract_placements(out)
    assert round(find(pl, "Bank 1")["y"] - find(pl, "Bank 0")["y"]) == 16

def test_column_paths_resolve_against_the_row_not_the_root(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc()), data(1), f1040_path)
    assert find(extract_placements(out), "100.00")

def test_rows_beyond_maxrows_are_not_drawn(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc(max_rows=2)), data(5), f1040_path)
    texts = " ".join(p["text"] for p in extract_placements(out))
    assert "Bank 1" in texts and "Bank 2" not in texts

def test_statement_target_prints_when_the_group_overflows(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc(max_rows=2)), data(5), f1040_path)
    assert find(extract_placements(out), "See attached statement")

def test_statement_target_is_suppressed_when_nothing_overflows(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc(max_rows=9)), data(2), f1040_path)
    assert not [p for p in extract_placements(out) if "attached statement" in p["text"]]

def test_error_strategy_raises_rather_than_dropping_rows(f1040_path):
    doc = group_doc(max_rows=2, strategy="error", target=None)
    with pytest.raises(ValueError, match="payers"):
        render(AnnotationSet.model_validate(doc), data(5), f1040_path)

def test_empty_array_draws_no_rows(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc()), {"income": {"interest": []}}, f1040_path)
    assert not [p for p in extract_placements(out) if "Bank" in p["text"]]
