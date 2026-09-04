"""Display strings -> glyphs on a transparent overlay, merged onto the
unmodified government PDF. Contains no JSONPath and no tax knowledge."""
import io
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader, PdfWriter

from app.models import AnnotationSet, FieldAnnotation, GroupAnnotation, Style
from app.geometry import to_pdf_rect, baseline_y, anchor_x
from app.formatter import format_value, COMB_TYPES
from app.resolver import resolve_one, resolve_many, evaluate


def _style(aset: AnnotationSet, ann: FieldAnnotation) -> Style:
    merged = aset.defaults.model_dump() | ann.style.model_dump(exclude_defaults=True)
    return Style.model_validate(merged)


def _font(s: Style) -> str:
    return s.font if s.fontFallback is None else s.fontFallback


def _fit(text: str, ann: FieldAnnotation, s: Style) -> float:
    """Return the size to draw at, honouring ann.overflow."""
    avail = ann.box.width - 2 * s.padding
    size = s.size
    if stringWidth(text, _font(s), size) <= avail:
        return size
    if ann.overflow == "error":
        raise ValueError(
            f"{ann.id}: {text!r} does not fit in a {ann.box.width}pt box")
    if ann.overflow == "shrink":
        while size > ann.minSize and stringWidth(text, _font(s), size) > avail:
            size -= 0.25
    return max(size, ann.minSize)


def _draw_field(c, aset, ann: FieldAnnotation, data, page_h: float):
    if not evaluate(ann.condition, data):
        return
    raw = resolve_one(ann.value, data, required=ann.required, annotation_id=ann.id)
    out = format_value(ann, raw)
    s = _style(aset, ann)
    c.saveState()
    c.setFillColor(s.color)
    if isinstance(out, list):                       # comb: one glyph per cell
        cells = ann.format.cells or len(out)
        pitch = ann.box.width / cells
        c.setFont(_font(s), s.size)
        y = baseline_y(ann.box, page_h, s)
        for i, ch in enumerate(out):
            if ch:
                cx = ann.box.x + pitch * i + (pitch - stringWidth(ch, _font(s), s.size)) / 2
                c.drawString(cx, y, ch)
    elif out:
        size = _fit(out, ann, s)
        s2 = s.model_copy(update={"size": size})
        c.setFont(_font(s2), size)
        if ann.overflow == "clip":
            path = c.beginPath()
            path.rect(*to_pdf_rect(ann.box, page_h))
            c.clipPath(path, stroke=0)
        c.drawString(anchor_x(ann.box, s2, stringWidth(out, _font(s2), size)),
                     baseline_y(ann.box, page_h, s2), out)
    c.restoreState()


def _draw_debug(c, ann_box, page_h: float, label: str):
    x, y, w, h = to_pdf_rect(ann_box, page_h)
    c.saveState()
    c.setStrokeColorRGB(1, 0, 0); c.setLineWidth(0.4)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFont("Helvetica", 4); c.setFillColorRGB(1, 0, 0)
    c.drawString(x, y + h + 0.5, label)
    c.restoreState()


def _overflow_targets(aset: AnnotationSet, data: dict) -> tuple[set[str], set[str]]:
    """Which 'see attached statement' annotations exist, and which fired.

    A field named by some group's overflowTarget is NOT part of the normal
    field pass — it prints only when that group actually overflows. Deciding
    this up front (instead of while drawing) keeps it correct when the group
    and its target sit on different pages.
    """
    declared: set[str] = set()
    fired: set[str] = set()
    for g in aset.annotations:
        if not isinstance(g, GroupAnnotation) or not g.overflowTarget:
            continue
        declared.add(g.overflowTarget)
        if evaluate(g.condition, data) and len(resolve_many(g.source, data)) > g.maxRows:
            fired.add(g.overflowTarget)
    return declared, fired


def render(aset: AnnotationSet, data: dict, pdf_path: Path, *, debug: bool = False) -> bytes:
    base = PdfReader(pdf_path)
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    by_page = {p.number: p for p in aset.pages}
    declared, fired = _overflow_targets(aset, data)

    for pno in sorted(by_page):
        page = by_page[pno]
        c.setPageSize((page.width, page.height))
        for ann in aset.annotations:
            if ann.page != pno:
                continue
            if isinstance(ann, FieldAnnotation):
                if ann.id in declared and ann.id not in fired:
                    continue
                _draw_field(c, aset, ann, data, page.height)
                if debug:
                    _draw_debug(c, ann.box, page.height, ann.id)
            else:
                _draw_group(c, aset, ann, data, page.height, debug)
        c.showPage()
    c.save()

    overlay = PdfReader(io.BytesIO(buf.getvalue()))
    writer = PdfWriter()
    for i, page in enumerate(base.pages):
        if i < len(overlay.pages):
            page.merge_page(overlay.pages[i])
        writer.add_page(page)
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


def _draw_group(c, aset, grp: GroupAnnotation, data, page_h: float, debug: bool):
    if not evaluate(grp.condition, data):
        return
    rows = resolve_many(grp.source, data)
    if len(rows) > grp.maxRows and grp.overflowStrategy == "error":
        raise ValueError(
            f"{grp.id}: {len(rows)} rows exceed maxRows={grp.maxRows}")
    for n, row in enumerate(rows[:grp.maxRows]):
        dy = n * grp.rowHeight
        for col in grp.columns:
            shifted = col.model_copy(deep=True)
            shifted.box = col.box.model_copy(
                update={"y": grp.firstRowBox.y + dy})
            shifted.id = f"{grp.id}[{n}].{col.id}"
            _draw_field(c, aset, shifted, row, page_h)
            if debug:
                _draw_debug(c, shifted.box, page_h, shifted.id)
