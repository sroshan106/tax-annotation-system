import hashlib, json
from pathlib import Path
from pypdf import PdfReader
from app.models import AnnotationSet


class SourceMismatch(RuntimeError): ...


def load_set(path: str | Path, *, strict: bool = False) -> AnnotationSet:
    return AnnotationSet.model_validate(json.loads(Path(path).read_text()))


def verify_source(aset: AnnotationSet, pdf_path: Path, *, strict: bool) -> list[str]:
    """The IRS reissues PDFs at the same URL, so a digest mismatch is a warning
    by default and an error only under --strict."""
    problems: list[str] = []
    digest = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
    if digest != aset.source.sha256:
        problems.append(
            f"sha256 mismatch: set pins {aset.source.sha256[:12]}…, "
            f"{pdf_path.name} is {digest[:12]}…")
    reader = PdfReader(pdf_path)
    if len(reader.pages) != aset.source.pageCount:
        problems.append(
            f"page count mismatch: set declares {aset.source.pageCount}, "
            f"PDF has {len(reader.pages)}")
    for p in aset.pages:
        if p.number > len(reader.pages):
            continue
        mb = reader.pages[p.number - 1].mediabox
        if (round(float(mb.width), 1), round(float(mb.height), 1)) != (p.width, p.height):
            problems.append(
                f"page {p.number} size mismatch: set declares "
                f"{p.width}x{p.height}, PDF is {float(mb.width)}x{float(mb.height)}")
    if problems and strict:
        raise SourceMismatch("; ".join(problems))
    return problems
