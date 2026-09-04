from app.models import Box, Style
from app.geometry import to_pdf_rect, baseline_y, anchor_x, CAP_HEIGHT_RATIO

PAGE_H = 792.0

def test_top_left_box_converts_to_pdf_bottom_left():
    b = Box(x=40, y=96, width=200, height=14)
    assert to_pdf_rect(b, PAGE_H) == (40.0, 792.0 - 96.0 - 14.0, 200.0, 14.0)

def test_conversion_round_trips():
    b = Box(x=10, y=0, width=5, height=792)
    x, y, w, h = to_pdf_rect(b, PAGE_H)
    assert y == 0.0 and h == 792.0

def test_middle_valign_centres_cap_height():
    b = Box(x=0, y=0, width=100, height=20)
    s = Style(size=10, valign="middle")
    cap = 10 * CAP_HEIGHT_RATIO
    expected = (792.0 - 0 - 20) + (20 - cap) / 2
    assert baseline_y(b, PAGE_H, s) == expected

def test_bottom_valign_uses_padding():
    b = Box(x=0, y=0, width=100, height=20)
    s = Style(size=10, valign="bottom", padding=2)
    assert baseline_y(b, PAGE_H, s) == (792.0 - 20) + 2

def test_right_align_inset_by_padding():
    b = Box(x=100, y=0, width=80, height=14)
    s = Style(align="right", padding=2)
    assert anchor_x(b, s, text_width=30) == 100 + 80 - 2 - 30

def test_centre_align_ignores_padding():
    b = Box(x=100, y=0, width=80, height=14)
    assert anchor_x(b, Style(align="center"), text_width=30) == 100 + (80 - 30) / 2
