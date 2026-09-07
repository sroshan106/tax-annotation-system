import json, pathlib, pytest
from app.loader import load_set, verify_source
from app.renderer import render
from app.models import FieldAnnotation, GroupAnnotation
from tests.pdf_probe import extract_placements

SETS = {"annotations/f1040-2024.json": "forms/f1040.pdf",
        "annotations/f1040sb-2024.json": "forms/f1040sb.pdf"}
EXAMPLES = ["examples/simple-w2.json", "examples/joint-dependents.json",
            "examples/schedule-b-normal.json", "examples/schedule-b-overflow.json"]


@pytest.mark.parametrize("set_path,pdf", SETS.items())
def test_shipped_sets_validate_and_match_their_pdf(set_path, pdf):
    aset = load_set(set_path)
    assert verify_source(aset, pathlib.Path(pdf), strict=False) == []


@pytest.mark.parametrize("set_path", SETS)
def test_no_placeholder_paths_survive(set_path):
    assert "TODO" not in pathlib.Path(set_path).read_text()


@pytest.mark.parametrize("set_path", SETS)
def test_every_box_sits_on_its_page(set_path):
    aset = load_set(set_path)
    pages = {p.number: p for p in aset.pages}
    for a in aset.annotations:
        pg = pages[a.page]
        if isinstance(a, FieldAnnotation):
            assert 0 <= a.box.x and a.box.x + a.box.width <= pg.width, a.id
            assert 0 <= a.box.y and a.box.y + a.box.height <= pg.height, a.id
        else:
            for c in a.columns:
                for n in (0, a.maxRows - 1):
                    assert a.row_box(c, n).fits(pg), f"{a.id}.{c.id} row {n}"


def test_the_1040_set_covers_every_declared_field_type():
    aset = load_set("annotations/f1040-2024.json")
    seen = {a.type for a in aset.annotations if isinstance(a, FieldAnnotation)}
    seen |= {c.type for a in aset.annotations if isinstance(a, GroupAnnotation)
             for c in a.columns}
    required = {"text", "currency", "date", "checkbox", "ssn", "zip", "integer"}
    assert required <= seen, f"missing: {required - seen}"


@pytest.mark.parametrize("example", EXAMPLES)
def test_every_example_renders_without_error(example):
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


def test_schedule_b_normal_does_not_overflow():
    aset = load_set("annotations/f1040sb-2024.json")
    grp = next(a for a in aset.annotations if isinstance(a, GroupAnnotation))
    data = json.loads(pathlib.Path("examples/schedule-b-normal.json").read_text())
    assert len(data["interest"]["payers"]) <= grp.maxRows


def test_exact_four_examples_exist():
    example_files = sorted(p.name for p in pathlib.Path("examples").glob("*.json"))
    expected = ["joint-dependents.json", "schedule-b-normal.json", "schedule-b-overflow.json", "simple-w2.json"]
    assert example_files == expected, f"expected exactly 4 examples (2 per form type), got {example_files}"


def test_1040_comprehensive_example_fills_all_data():
    aset = load_set("annotations/f1040-2024.json")
    data = json.loads(pathlib.Path("examples/joint-dependents.json").read_text())
    from app.resolver import resolve_one, resolve_many
    # All 4 rows in dependents table are populated
    dependents = resolve_many("$.dependents[*]", data)
    assert len(dependents) >= 4, f"expected at least 4 dependents, got {len(dependents)}"
    # Continuation checkbox condition is met
    assert data.get("dependentsContinuedOnStatement") is True, "expected dependentsContinuedOnStatement to be true"
    # Every non-checkbox field has a resolved value
    for a in aset.annotations:
        if isinstance(a, FieldAnnotation) and a.type != "checkbox":
            val = resolve_one(a.value, data, required=False, annotation_id=a.id)
            assert val is not None, f"expected field {a.id} ({a.value}) to be filled"


def test_schedule_b_comprehensive_example_fills_all_data():
    aset = load_set("annotations/f1040sb-2024.json")
    data = json.loads(pathlib.Path("examples/schedule-b-overflow.json").read_text())
    from app.resolver import resolve_one, resolve_many
    # All 13 rows in payers table are populated (and exceeds to trigger overflow)
    payers = resolve_many("$.interest.payers[*]", data)
    grp = next(a for a in aset.annotations if isinstance(a, GroupAnnotation))
    assert len(payers) > grp.maxRows, f"expected > {grp.maxRows} payers, got {len(payers)}"
    # Every field has a resolved value
    for a in aset.annotations:
        if isinstance(a, FieldAnnotation):
            val = resolve_one(a.value, data, required=False, annotation_id=a.id)
            assert val is not None, f"expected field {a.id} ({a.value}) to be filled"

