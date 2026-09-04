import json, pathlib, pytest
from app.loader import load_set, verify_source
from app.renderer import render
from app.models import FieldAnnotation, GroupAnnotation
from tests.pdf_probe import extract_placements

SETS = {"annotations/f1040-2024.json": "forms/f1040.pdf",
        "annotations/f1040sb-2024.json": "forms/f1040sb.pdf"}
EXAMPLES = ["examples/simple-w2.json", "examples/joint-dependents.json",
            "examples/schedule-b-overflow.json"]


@pytest.mark.parametrize("set_path,pdf", SETS.items())
def test_shipped_sets_validate_and_match_their_pdf(set_path, pdf):
    aset = load_set(set_path)
    assert verify_source(aset, pathlib.Path(pdf), strict=False) == []


@pytest.mark.parametrize("set_path,pdf", SETS.items())
def test_no_placeholder_paths_survive(set_path, pdf):
    assert "TODO" not in pathlib.Path(set_path).read_text()


@pytest.mark.parametrize("set_path,pdf", SETS.items())
def test_every_box_sits_on_its_page(set_path, pdf):
    aset = load_set(set_path)
    pages = {p.number: p for p in aset.pages}
    for a in aset.annotations:
        boxes = [a.box] if isinstance(a, FieldAnnotation) else [a.firstRowBox]
        for b in boxes:
            pg = pages[a.page]
            assert 0 <= b.x and b.x + b.width <= pg.width, a.id
            assert 0 <= b.y and b.y + b.height <= pg.height, a.id


def test_the_1040_set_covers_every_declared_field_type():
    aset = load_set("annotations/f1040-2024.json")
    seen = {a.type for a in aset.annotations if isinstance(a, FieldAnnotation)}
    seen |= {c.type for a in aset.annotations if isinstance(a, GroupAnnotation)
             for c in a.columns}
    required = {"text", "currency", "date", "checkbox", "ssn", "zip", "integer"}
    assert required <= seen, f"missing: {required - seen}"


@pytest.mark.parametrize("example", EXAMPLES)
def test_every_example_renders_without_error(example, f1040_path):
    data = json.loads(pathlib.Path(example).read_text())
    target = "annotations/f1040sb-2024.json" if "schedule-b" in example \
             else "annotations/f1040-2024.json"
    pdf = SETS[target]
    out = render(load_set(target), data, pathlib.Path(pdf))
    assert extract_placements(out), "nothing was drawn"


def test_schedule_b_example_overflows_its_group():
    aset = load_set("annotations/f1040sb-2024.json")
    grp = next(a for a in aset.annotations if isinstance(a, GroupAnnotation))
    data = json.loads(pathlib.Path("examples/schedule-b-overflow.json").read_text())
    assert len(data["interest"]["payers"]) > grp.maxRows
