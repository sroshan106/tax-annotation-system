import argparse, json
from pathlib import Path
from app.loader import load_set, verify_source
from app.renderer import render
from app.routes import FORMS


def main(argv=None):
    p = argparse.ArgumentParser(description="Render filled PDF from annotation set and dataset")
    p.add_argument("annotation_set", help="Path to annotation set JSON")
    p.add_argument("dataset", help="Path to dataset JSON")
    p.add_argument("-o", "--out", required=True, help="Output PDF path")
    p.add_argument("--debug", action="store_true", help="Draw debug bounding boxes")
    p.add_argument("--strict", action="store_true", help="Enforce strict source verification")
    a = p.parse_args(argv)

    aset = load_set(a.annotation_set)
    target = Path(a.annotation_set).resolve()
    pdf_path = next((pdf for s, pdf in FORMS.values() if Path(s).resolve() == target), None)
    if not pdf_path:
        raise SystemExit(f"No registered form matching annotation set {a.annotation_set!r}")

    for w in verify_source(aset, pdf_path, strict=a.strict):
        print(f"warning: {w}")
    Path(a.out).write_bytes(
        render(aset, json.loads(Path(a.dataset).read_text()), pdf_path, debug=a.debug))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
