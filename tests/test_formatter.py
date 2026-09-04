import pytest
from app.models import FieldAnnotation, Box, Format
from app.formatter import format_value

def ann(type_, **fmt):
    return FieldAnnotation(id="t", label="t", page=1,
                           box=Box(x=0, y=0, width=100, height=14),
                           type=type_, value="$.x", format=Format(**fmt))

@pytest.mark.parametrize("raw,expected", [
    (52000.0, "52,000.00"),
    (0, ""),                       # zeroSuppress default
    (-1234.5, "(1,234.50)"),
    (1234.567, "1,234.57"),        # half-even at 2dp
])
def test_currency(raw, expected):
    assert format_value(ann("currency"), raw) == expected

def test_currency_whole_dollars_rounds_and_drops_cents():
    assert format_value(ann("currency", wholeDollars=True), 1234.56) == "1,235"

def test_currency_minus_convention():
    assert format_value(ann("currency", negative="minus"), -12.0) == "-12.00"

def test_currency_zero_not_suppressed_when_disabled():
    assert format_value(ann("currency", zeroSuppress=False), 0) == "0.00"

def test_none_always_renders_empty():
    assert format_value(ann("currency"), None) == ""
    assert format_value(ann("text"), None) == ""

def test_currency_suppresses_subcent_value_that_rounds_to_zero():
    assert format_value(ann("currency"), -0.004) == ""

def test_currency_whole_dollars_suppresses_value_rounding_to_zero():
    assert format_value(ann("currency", wholeDollars=True), 0.4) == ""

def test_currency_at_two_decimals_still_prints_real_subdollar_amount():
    assert format_value(ann("currency"), 0.4) == "0.40"

def test_currency_zero_suppress_disabled_prints_zero_not_empty_for_rounds_to_zero():
    assert format_value(ann("currency", zeroSuppress=False), -0.004) == "0.00"

def test_ssn_comb_returns_nine_cells():
    cells = format_value(ann("ssn", cells=9), "123-45-6789")
    assert cells == list("123456789")

def test_comb_pads_short_values_and_rejects_long_ones():
    assert format_value(ann("zip", cells=5), "021") == ["0", "2", "1", "", ""]
    with pytest.raises(ValueError, match="9 cells"):
        format_value(ann("ssn", cells=9), "1234567890")

def test_date_uses_pattern():
    assert format_value(ann("date"), "2025-04-15") == "04/15/2025"

def test_date_rejects_non_iso_input():
    with pytest.raises(ValueError, match="ISO 8601"):
        format_value(ann("date"), "April 15 2025")

@pytest.mark.parametrize("raw,expected", [(True, "X"), ("yes", "X"), (1, "X"),
                                          (False, ""), (None, ""), ("no", "")])
def test_checkbox(raw, expected):
    assert format_value(ann("checkbox"), raw) == expected

def test_integer_and_text_passthrough():
    assert format_value(ann("integer"), 3) == "3"
    assert format_value(ann("text"), "Ada Lovelace") == "Ada Lovelace"
