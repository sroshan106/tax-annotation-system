"""AcroForm widget rects -> a draft annotation set.

The IRS ships the box geometry inside the PDF. Extract it, then a human names
each annotation and assigns its JSONPath. Draft output is a starting point,
not a deliverable: it is filtered down to the representative subset by hand.
"""
import hashlib, json, re, sys
from pathlib import Path
from pypdf import PdfReader
from pypdf.generic import IndirectObject

_MAX_PARENT_DEPTH = 64  # ponytail: bound against a malformed/cyclic /Parent chain


def infer_type(field_name: str, ft: str) -> str:
    if ft == "/Btn":
        return "checkbox"
    return "text"


def _slug(name: str, n: int) -> str:
    tail = re.sub(r"[^0-9a-zA-Z]+", "_", name.split(".")[-1]).strip("_").lower()
    return f"{tail or 'field'}_{n}"


def _resolve(obj):
    return obj.get_object() if isinstance(obj, IndirectObject) else obj


def extract(pdf_path: Path, form_id: str, tax_year: int) -> dict:
    pdf_path = Path(pdf_path)
    reader = PdfReader(pdf_path)
    annotations, n = [], 0
    for pno, page in enumerate(reader.pages, start=1):
        page_h = float(page.mediabox.height)
        annots = _resolve(page.get("/Annots")) or []
        for ref in annots:
            w = _resolve(ref)
            if w.get("/Subtype") != "/Widget":
                continue
            fld = w
            depth = 0
            while fld is not None and "/T" not in fld and depth < _MAX_PARENT_DEPTH:
                fld = _resolve(fld.get("/Parent"))
                depth += 1
            if fld is None or "/T" not in fld:
                continue
            name = _full_name(fld)
            x0, y0, x1, y1 = (float(v) for v in w["/Rect"])
            n += 1
            annotations.append({
                "kind": "field",
                "id": _slug(name, n),
                "label": name,
                "page": pno,
                # PDF bottom-left -> spec top-left, the inverse of geometry.to_pdf_rect
                "box": {"x": round(min(x0, x1), 2),
                        "y": round(page_h - max(y0, y1), 2),
                        "width": round(abs(x1 - x0), 2),
                        "height": round(abs(y1 - y0), 2)},
                "type": infer_type(name, str(fld.get("/FT", "/Tx"))),
                "value": "$.TODO_assign_a_path",
                "acroFieldName": name,
            })
    return {
        "specVersion": "1.0",
        "form": {"id": form_id, "title": f"{form_id} {tax_year}",
                 "taxYear": tax_year, "revision": str(tax_year),
                 "jurisdiction": "US-IRS"},
        "source": {"url": f"https://www.irs.gov/pub/irs-pdf/{pdf_path.name}",
                   "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                   "pageCount": len(reader.pages)},
        "pages": [{"number": i, "width": round(float(p.mediabox.width), 2),
                   "height": round(float(p.mediabox.height), 2)}
                  for i, p in enumerate(reader.pages, start=1)],
        "annotations": annotations,
    }


def _full_name(fld) -> str:
    parts, cur, depth = [], fld, 0
    while cur is not None and depth < _MAX_PARENT_DEPTH:
        if "/T" in cur:
            parts.append(str(cur["/T"]))
        cur = _resolve(cur.get("/Parent"))
        depth += 1
    return ".".join(reversed(parts))


if __name__ == "__main__":
    pdf, form_id, year = sys.argv[1], sys.argv[2], int(sys.argv[3])
    print(json.dumps(extract(Path(pdf), form_id, year), indent=2))
