import pytest
from app.models import Condition
from app.resolver import (resolve_one, resolve_many, evaluate,
                          MissingValueError, MultipleMatchesError, UnsupportedPathError)

DATA = {
    "taxpayer": {"firstName": "Ada", "ssn": "123456789", "spouse": None},
    "income": {"w2": [{"wages": 52000.0}, {"wages": 8000.0}],
               "interest": [{"payer": "Acme Bank", "amount": 120.5}]},
    "filingStatus": "single",
}

def test_child_access():
    assert resolve_one("$.taxpayer.firstName", DATA, required=False, annotation_id="t") == "Ada"

def test_array_index():
    assert resolve_one("$.income.w2[0].wages", DATA, required=False, annotation_id="t") == 52000.0

def test_missing_path_returns_none():
    assert resolve_one("$.taxpayer.middleName", DATA, required=False, annotation_id="t") is None

def test_missing_required_path_raises_naming_the_annotation():
    with pytest.raises(MissingValueError, match="line_1a"):
        resolve_one("$.nope", DATA, required=True, annotation_id="line_1a")

def test_explicit_null_is_treated_as_absent():
    assert resolve_one("$.taxpayer.spouse", DATA, required=False, annotation_id="t") is None

def test_multiple_matches_on_a_field_is_an_error():
    with pytest.raises(MultipleMatchesError, match="2 matches"):
        resolve_one("$.income.w2[*].wages", DATA, required=False, annotation_id="t")

def test_resolve_many_returns_all_matches_in_document_order():
    assert resolve_many("$.income.w2[*].wages", DATA) == [52000.0, 8000.0]

def test_resolve_many_on_missing_path_is_empty():
    assert resolve_many("$.income.k1[*]", DATA) == []

def test_filter_expressions_are_rejected():
    with pytest.raises(UnsupportedPathError):
        resolve_many("$.income.w2[?(@.wages > 1000)]", DATA)

def test_condition_none_always_prints():
    assert evaluate(None, DATA) is True

@pytest.mark.parametrize("cond,expected", [
    (Condition(path="$.filingStatus", op="equals", value="single"), True),
    (Condition(path="$.filingStatus", op="equals", value="mfj"), False),
    (Condition(path="$.filingStatus", op="notEquals", value="mfj"), True),
    (Condition(path="$.taxpayer.firstName", op="exists"), True),
    (Condition(path="$.taxpayer.middleName", op="exists"), False),
    (Condition(path="$.taxpayer.middleName", op="absent"), True),
    (Condition(path="$.taxpayer.spouse", op="truthy"), False),
])
def test_conditions(cond, expected):
    assert evaluate(cond, DATA) is expected
