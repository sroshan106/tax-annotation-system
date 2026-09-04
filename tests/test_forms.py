from pypdf import PdfReader

def test_1040_is_two_letter_pages(f1040_path):
    r = PdfReader(f1040_path)
    assert len(r.pages) == 2
    box = r.pages[0].mediabox
    assert (float(box.width), float(box.height)) == (612.0, 792.0)

def test_schedule_b_geometry_is_measured_not_assumed(f1040sb_path):
    r = PdfReader(f1040sb_path)
    box = r.pages[0].mediabox
    # Assert what is actually there; do not assume Letter.
    assert (float(box.width), float(box.height)) == (612.0, 792.0)
    assert len(r.pages) >= 1
