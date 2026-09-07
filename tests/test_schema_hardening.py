"""Covers the schema-hardening findings: default merging, honest group
geometry, per-type format keys, and load-time bounds checking."""
import pytest
from pydantic import ValidationError

from app.models import AnnotationSet
from app.renderer import render
from tests.pdf_probe import extract_placements, find
from tests.test_models import MINIMAL

DATA = {"taxpayer": {"firstName": "Ada"}}


def currency_doc(defaults=None, fmt=None):
    ann = {"kind": "field", "id": "amount", "label": "Amount", "page": 1,
           "box": {"x": 40, "y": 200, "width": 120, "height": 14},
           "type": "currency", "value": "$.amount"}
    if fmt is not None:
        ann["format"] = fmt
    doc = {**MINIMAL, "annotations": [ann]}
    if defaults is not None:
        doc["defaults"] = defaults
    return doc


def group_doc(**over):
    grp = {"kind": "group", "id": "payers", "label": "Payers", "page": 1,
           "source": "$.income.interest[*]", "rowHeight": 16, "maxRows": 2,
           "firstRowY": 300.0,
           "overflowStrategy": "error",
           "columns": [{"id": "payer", "label": "Payer", "x": 40, "width": 280,
                        "type": "text", "value": "$.name"}]}
    grp.update(over)
    return {**MINIMAL, "annotations": [grp]}


# --- 1. default merging -------------------------------------------------

def test_annotation_overrides_a_set_default_with_a_class_default_value(f1040_path):
    """align:'left' happens to be the class default, but the annotation set
    them explicitly, so it must beat defaults.style.align:'right'."""
    doc = {**MINIMAL,
           "defaults": {"style": {"align": "right"}},
           "annotations": [{**MINIMAL["annotations"][0], "style": {"align": "left"}}]}
    p = find(extract_placements(render(AnnotationSet.model_validate(doc), DATA, f1040_path)), "Ada")
    box = MINIMAL["annotations"][0]["box"]
    assert p["x"] == pytest.approx(box["x"] + 1.5, abs=0.6)


def test_set_default_still_applies_when_the_annotation_is_silent(f1040_path):
    doc = {**MINIMAL, "defaults": {"style": {"align": "right"}},
           "annotations": [MINIMAL["annotations"][0]]}
    p = find(extract_placements(render(AnnotationSet.model_validate(doc), DATA, f1040_path)), "Ada")
    box = MINIMAL["annotations"][0]["box"]
    assert p["x"] > box["x"] + box["width"] / 2


# --- 6. format defaults -------------------------------------------------

def test_set_level_format_defaults_reach_annotations(f1040_path):
    doc = currency_doc(defaults={"format": {"negative": "minus"}})
    out = render(AnnotationSet.model_validate(doc), {"amount": -12.5}, f1040_path)
    assert find(extract_placements(out), "12.50")["text"].startswith("-")


def test_annotation_format_beats_the_set_default(f1040_path):
    doc = currency_doc(defaults={"format": {"negative": "minus"}},
                       fmt={"negative": "parentheses"})
    out = render(AnnotationSet.model_validate(doc), {"amount": -12.5}, f1040_path)
    assert "(" in find(extract_placements(out), "12.50")["text"]


# --- 5. format keys must match the field type ---------------------------

def test_format_key_irrelevant_to_the_type_is_rejected():
    with pytest.raises(ValidationError, match="wholeDollars"):
        AnnotationSet.model_validate(
            {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
                                         "type": "date",
                                         "format": {"wholeDollars": True}}]})


def test_format_key_relevant_to_the_type_is_accepted():
    AnnotationSet.model_validate(currency_doc(fmt={"wholeDollars": True}))


def test_format_defaults_are_exempt_from_the_per_type_check():
    """defaults.format is shared across every type, so it cannot be
    restricted to one type's keys."""
    AnnotationSet.model_validate(currency_doc(defaults={"format": {"negative": "minus"}}))


# --- 2/3/4. group geometry ----------------------------------------------

def test_group_rows_start_at_firstrowy_and_step_by_rowheight(f1040_path):
    data = {"income": {"interest": [{"name": "Bank 0"}, {"name": "Bank 1"}]}}
    pl = extract_placements(render(AnnotationSet.model_validate(group_doc()), data, f1040_path))
    assert find(pl, "Bank 0")["y"] == pytest.approx(300 + 16 / 2, abs=6)
    assert round(find(pl, "Bank 1")["y"] - find(pl, "Bank 0")["y"]) == 16


def test_group_columns_reject_the_dead_page_and_y_keys():
    """A column carries only x and width; page and y were never read."""
    with pytest.raises(ValidationError):
        AnnotationSet.model_validate(group_doc(columns=[
            {"kind": "field", "id": "payer", "label": "Payer", "page": 1,
             "box": {"x": 40, "y": 300, "width": 280, "height": 14},
             "type": "text", "value": "$.name"}]))


def test_comb_columns_still_require_cells():
    with pytest.raises(ValidationError, match="cells"):
        AnnotationSet.model_validate(group_doc(columns=[
            {"id": "ssn", "label": "SSN", "x": 40, "width": 100,
             "type": "comb", "value": "$.ssn"}]))


# --- 7. load-time bounds checking ---------------------------------------

def test_box_running_off_its_page_is_rejected():
    with pytest.raises(ValidationError, match="does not fit on page 1"):
        AnnotationSet.model_validate(
            {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
                                         "box": {"x": 560, "y": 96,
                                                 "width": 200, "height": 14}}]})


def test_negative_coordinates_are_rejected():
    with pytest.raises(ValidationError, match="does not fit on page 1"):
        AnnotationSet.model_validate(
            {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
                                         "box": {"x": -1, "y": 96,
                                                 "width": 200, "height": 14}}]})


def test_group_whose_rows_would_run_past_the_page_is_rejected():
    with pytest.raises(ValidationError, match="does not fit on page 1"):
        AnnotationSet.model_validate(group_doc(firstRowY=700.0, rowHeight=16, maxRows=20))


def test_group_column_wider_than_its_page_is_rejected():
    with pytest.raises(ValidationError, match="does not fit on page 1"):
        AnnotationSet.model_validate(group_doc(columns=[
            {"id": "payer", "label": "Payer", "x": 500, "width": 200,
             "type": "text", "value": "$.name"}]))
