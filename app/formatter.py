from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
import re
from app.models import FieldAnnotation

COMB_TYPES = {"ssn", "ein", "zip", "phone", "comb"}


def format_value(ann: FieldAnnotation, raw):
    f = ann.format
    if raw is None:
        return [""] * f.cells if (ann.type in COMB_TYPES and f.cells) else ""
    if ann.type == "checkbox":
        return f.checkedGlyph if raw in f.trueValues else ""
    if ann.type in ("currency", "decimal"):
        return _money(Decimal(str(raw)), ann)
    if ann.type == "date":
        return _date(raw, f.datePattern)
    if ann.type in COMB_TYPES and f.cells:
        digits = re.sub(r"[^0-9A-Za-z]", "", str(raw))
        if len(digits) > f.cells:
            raise ValueError(f"{ann.id}: {raw!r} does not fit in {f.cells} cells")
        return list(digits) + [""] * (f.cells - len(digits))
    return str(raw)


def _money(v: Decimal, ann: FieldAnnotation) -> str:
    f = ann.format
    places = 0 if f.wholeDollars else f.decimals
    # Banker's rounding eliminates cumulative rounding bias across multiple schedule lines.
    v = v.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
    # Check post-rounding value: prevents tiny fractions from producing unwanted 0.00 entries.
    if f.zeroSuppress and v == 0:
        return ""
    sep = "," if f.thousandsSeparator else ""
    body = f"{abs(v):{sep}.{places}f}"
    if not (v < 0):
        return body
    return f"({body})" if f.negative == "parentheses" else f"-{body}"


def _date(raw, pattern: str) -> str:
    if isinstance(raw, (date, datetime)):
        return raw.strftime(pattern)
    try:
        return date.fromisoformat(str(raw)).strftime(pattern)
    except ValueError as exc:
        raise ValueError(f"date values must be ISO 8601 (YYYY-MM-DD); got {raw!r}") from exc
