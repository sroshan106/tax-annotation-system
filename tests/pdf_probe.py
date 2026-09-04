"""Read back what was actually drawn. Used instead of golden-byte comparison,
which is impossible: reportlab writes a nondeterministic /ID and timestamp."""
import io
from pypdf import PdfReader


def extract_placements(pdf_bytes: bytes, page: int = 0) -> list[dict]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pg = reader.pages[page]
    height = float(pg.mediabox.height)
    out: list[dict] = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            out.append({"text": text, "x": tm[4],
                        "y": height - tm[5], "size": font_size})

    pg.extract_text(visitor_text=visitor)
    return out


def find(placements: list[dict], needle: str) -> dict:
    hits = [p for p in placements if needle in p["text"]]
    assert hits, f"{needle!r} not found; got {[p['text'] for p in placements]}"
    return hits[0]
