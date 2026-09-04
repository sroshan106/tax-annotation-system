"""The ONLY place the spec's top-left coordinate system meets PDF user space.

Spec:  origin top-left, y grows down, unit = 1/72 inch.
PDF:   origin bottom-left, y grows up, same unit.
"""
from app.models import Box, Style

CAP_HEIGHT_RATIO = 0.72  # pinned by the spec so two renderers agree


def to_pdf_rect(box: Box, page_height: float) -> tuple[float, float, float, float]:
    return (box.x, page_height - box.y - box.height, box.width, box.height)


def baseline_y(box: Box, page_height: float, style: Style) -> float:
    _, y_bottom, _, h = to_pdf_rect(box, page_height)
    cap = style.size * CAP_HEIGHT_RATIO
    if style.valign == "bottom":
        return y_bottom + style.padding
    if style.valign == "top":
        return y_bottom + h - style.padding - cap
    return y_bottom + (h - cap) / 2


def anchor_x(box: Box, style: Style, text_width: float) -> float:
    if style.align == "right":
        return box.x + box.width - style.padding - text_width
    if style.align == "center":
        return box.x + (box.width - text_width) / 2
    return box.x + style.padding
