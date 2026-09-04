import pytest
from app.models import FieldAnnotation, Box, Format
from app.formatter import format_value

def ann(type_, **fmt):
    return FieldAnnotation(id="t", label="t", page=1,
                           box=Box(x=0, y=0, width=100, height=14),
                           type=type_, value="$.x", format=Format(**fmt))

@pytest.mark.parametrize("fmt,raw,expected", [
    ({}, 52000.0, "52,000.00"),
    ({}, 0, ""),
    ({}, -1234.5, "(1,234.50)"),
    ({}, 1234.567, "1,234.57"),
    ({}, -0.004, ""),
    ({}, 0.4, "0.40"),
    ({"wholeDollars": True}, 1234.56, "1,235"),
    ({"wholeDollars": True}, 0.4, ""),
    ({"negative": "minus"}, -12.0, "-12.00"),
    ({"zeroSuppress": False}, 0, "0.00"),
    ({"zeroSuppress": False}, -0.004, "0.00"),
])
def test_currency(fmt, raw, expected):
    assert format_value(ann("currency", **fmt), raw) == expected

def test_none_always_renders_empty():
    assert format_value(ann("currency"), None) == ""
    assert format_value(ann("text"), None) == ""

def test_ssn_comb_returns_nine_cells():
    assert format_value(ann("ssn", cells=9), "123-45-6789") == list("123456789")

def test_comb_pads_short_values_and_rejects_long_ones():
    assert format_value(ann("zip", cells=5), "021") == ["0", "2", "1", "", ""]
    with pytest.raises(ValueError, match="9 cells"):
        format_value(ann("ssn", cells=9), "1234567890")

def test_date():
    assert format_value(ann("date"), "2025-04-15") == "04/15/2025"
    with pytest.raises(ValueError, match="ISO 8601"):
        format_value(ann("date"), "April 15 2025")

@pytest.mark.parametrize("raw,expected", [(True, "X"), ("yes", "X"), (1, "X"),
                                          (False, ""), (None, ""), ("no", "")])
def test_checkbox(raw, expected):
    assert format_value(ann("checkbox"), raw) == expected

def test_passthrough():
    assert format_value(ann("integer"), 3) == "3"
    assert format_value(ann("text"), "Ada Lovelace") == "Ada Lovelace"

@pytest.mark.parametrize("fmt,raw,expected", [
    ({}, 42.5, "42.50"),
    ({"decimals": 1}, 42.5, "42.5"),
    ({}, 1234.567, "1,234.57"),
])
def test_decimal(fmt, raw, expected):
    assert format_value(ann("decimal", **fmt), raw) == expected

