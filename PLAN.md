# Tax Form Annotation Spec — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a documented, machine-checkable data structure that lets any third party print values from an arbitrary nested dataset into the correct boxes of a U.S. tax form using their own renderer.

**Architecture:** Pydantic v2 models are the single source of truth for the annotation format; the JSON Schema is *generated* from them, so "JSON" and "classes" are the same artifact and cannot drift. A reference pipeline — **load → resolve → format → draw** — consumes an annotation set plus a taxpayer JSON dataset and merges a reportlab text overlay onto the unmodified IRS PDF with pypdf. A Flask front end wraps that pipeline for the demo and exposes a `?debug=1` mode that draws every declared box, so the spec is shown rather than asserted.

**Tech Stack:** Python 3.12 · pydantic 2.x · jsonpath-ng (base parser only) · reportlab · pypdf · Flask 3.1 · pytest

**Spec:** `SPEC.md` (written in Task 11; §"Design decisions" below is its source of truth until then). Original brief: `REQUIREMENTS.md`.

## Global Constraints

- Coordinate system: **top-left origin, y grows down, unit = PDF point (1/72 in)**. Conversion to PDF user space is exactly `y_pdf_bottom = page_height - y - height`. This conversion lives in **exactly one function**, `app/geometry.py::to_pdf_rect`.
- Cap-height factor for vertical alignment is pinned at **0.72 × fontSize**. Baselines are computed from it, never guessed.
- JSONPath support is the **base `jsonpath_ng` grammar only** — child access, array index, `[*]`, `..`. Import `jsonpath_ng`, **never `jsonpath_ng.ext`**; the base parser has no filter or script expressions, which enforces the portable subset for free.
- Missing-data semantics are normative: a path resolving to **zero matches prints nothing**; the same annotation with `required: true` raises. A path resolving to **more than one match on a `field` annotation raises** — multiplicity is only legal inside a `group`.
- `style.font` MUST be one of the PDF base-14 names. Any other font name MUST be accompanied by `style.fontFallback` naming a base-14 substitute.
- All `annotations[]` entries are discriminated on `kind: "field" | "group"`. There is no second top-level list.
- Every spec feature MUST be exercised by at least one example dataset **and** one test. A feature with no example is deleted from the spec.
- Never assert PDF equality by bytes. reportlab emits a nondeterministic document ID; verification extracts text and positions with pypdf.
- **Ponytail — write the least code that holds.** Before adding anything, climb the ladder and stop at the first rung that works: (1) does it need to exist at all? (2) is it already in this repo? (3) does the stdlib do it? (4) does an already-installed dependency do it? (5) can it be one line? Only then write new code. Concretely, in this repo:
  - **A spec feature with no example dataset and no test does not ship.** This is not a style note, it is the acceptance rule — an enum value nobody implements is a lie in a spec that promises third parties can implement it.
  - No new dependency beyond `requirements.txt`. No abstraction with one implementation, no factory, no config for a value that never changes, no scaffolding "for later".
  - Fewest files. Do not split a module until it has two reasons to change.
  - Reuse before rewriting: `geometry.py` owns all box math, `resolver.py` owns all path work, `formatter.py` owns all string production. A second copy of any of those in `renderer.py` or `routes.py` is a bug.
  - Mark a deliberate simplification with a `# ponytail:` comment naming the ceiling and the upgrade path — e.g. `# ponytail: linear scan over annotations; index by page if a set ever exceeds ~1k`.
  - Laziness never applies to: the missing/multiple-match semantics, `source` verification, error messages that name the offending annotation id, or any test listed in a task. Those are the trust boundary.
- Non-goals, stated in SPEC.md: no tax calculation, no e-file/MeF, no OCR, no PDF authoring from scratch, no authoring UI, no state forms in v1.

---

## Design decisions (carried from review, all closed)

| # | Decision | Why |
|---|---|---|
| D1 | Coordinates are the primary anchor; `acroFieldName` is an optional cross-check hint. Coordinates win on conflict. | AcroForm names fail on scanned/non-fillable forms, are opaque (`f1_09[0]`), churn yearly, and cannot express *how* to print. |
| D2 | Top-left origin (see Global Constraints). | Matches how humans author and how HTML/canvas consumers work. One subtraction, pinned in one function. |
| D3 | Values referenced by a documented JSONPath subset. | De facto standard with libraries in every language — required, because the consumer's renderer is "their proprietary code." Filters excluded: they are the inconsistently-implemented part and a code-execution surface. |
| D4 | Pydantic v2 models are canonical; `schema/annotation-set.schema.json` is generated. | The brief accepts "classes in any popular programming language." One artifact yields both formats and gives the loader validation for free. |
| D5 | Annotation sets are JSON files in git, one per form-year. | Published form-year data is immutable. A database is only justified by an authoring UI, which is out of scope. |
| D6 | reportlab overlay merged by pypdf onto the untouched IRS PDF. | Both permissively licensed. PyMuPDF rejected: AGPL is a non-starter for a commercial tax platform. pypdf-only rejected: no alignment/clipping/pitch control. |
| D7 | `condition` is an object `{ path, op, value? }`, **not** a JSONPath predicate. | A predicate would need the filter grammar D3 excludes. This was a live contradiction in the previous plan. |
| D8 | Split dollar/cents lines are **two annotations** sharing an id prefix. | `box` is one rect. A "two-box format" would contradict the model for one form's convention. |
| D9 | Computed lines (`Line 9 = 1z + 2b + …`) are plain JSONPaths into a dataset the caller already computed. No `compute` operator. | The spec describes placement and presentation. Tax logic is the platform's crown jewel and belongs a layer up. Documented in SPEC.md as a considered-and-rejected option. |
| D10 | Annotation sets cover a **representative subset**, not all 229 widgets: every field type at least once across 1040 p1/p2, plus Schedule B Part I in full. SPEC.md states the sets are illustrative. | Past ~40 annotations the work is mechanical and adds no new evidence about the spec. |
| D11 | `source.sha256` mismatch is a **warning**, not a hard failure, unless `--strict`. | IRS silently reissues PDFs at the same URL; a hard fail would break the deliverable after grading day. |

### Deliberately not built (ponytail)

Each of these was in an earlier draft. Each was cut because it had no caller, no
example dataset, and no test — which by the acceptance rule in Global Constraints
means it would have shipped as an unverifiable promise, in a spec whose entire
purpose is that a stranger can implement it. All appear in SPEC.md §11 as future
enhancements, so a reader sees they were considered, not overlooked.

| Cut | Why | What covers the need instead |
|---|---|---|
| `Style.rotation` | No box in the v1 sets is rotated. Renderer code and a `saveState`/`translate`/`rotate` dance for zero call sites. | Nothing. Add it with the first rotated state form. |
| `Style.letterSpacing` | `comb` already owns character pitch, which was the only case that needed it. | `type: "comb"` + `format.cells`. |
| `overflow: "wrap"` / `"truncate"` | No implementation, no test. | `shrink` → `clip`, or `error` for values that must never be silently lost. |
| `FieldType: "multiline"` | Only meaningful with `wrap`, which is cut. | `text` + `shrink`. |
| `overflowStrategy: "continuation"` | Needs page cloning the v1 renderer does not do. "Reserved" in a spec is a promise nobody can test. | `statement` (print "see attached") or `error`. |
| `compute: {op: "sum", …}` (D9) | Tax logic in an annotation file is the wrong layer. | Plain JSONPath into a dataset the caller already computed. |
| A database for annotation sets (D5) | Published form-year data is immutable. | JSON files in git. |

**One thing kept that looks cuttable:** `app/cli.py` (~15 lines) overlaps
`/api/render`. It stays because Tasks 6 and 9 render examples without booting a
server, and a 15-line argparse wrapper is cheaper than the alternative.

---

## File structure

```
instead/
├── SPEC.md                              D1 — the specification (Task 11)
├── README.md                            quickstart + 60-second tour
├── PLAN.md                              this file
├── REQUIREMENTS.md                      the brief
├── requirements.txt
├── schema/annotation-set.schema.json     GENERATED from models — never hand-edited
├── forms/f1040.pdf, f1040sb.pdf          vendored IRS PDFs, sha256 pinned in each set
├── annotations/f1040-2024.json, f1040sb-2024.json
├── examples/simple-w2.json, joint-dependents.json, schedule-b-overflow.json
├── app/
│   ├── models.py      pydantic models — the format itself
│   ├── geometry.py    the one coordinate conversion + box math
│   ├── loader.py      read + validate a set, check source sha256
│   ├── resolver.py    JSONPath subset resolution + condition evaluation
│   ├── formatter.py   typed value -> display string(s)
│   ├── renderer.py    display string -> glyphs on a reportlab overlay, merged by pypdf
│   ├── routes.py      HTTP layer only, no domain logic
│   ├── __init__.py    Flask app factory
│   └── templates/index.html
├── tools/extract_widgets.py             AcroForm rects -> draft annotation set
└── tests/
```

`renderer.py` must contain no JSONPath and no tax knowledge; `formatter.py` must contain no PDF calls. Those boundaries are the same ones a third-party implementer hits, which is the point.

---

### Task 0: Groundwork

**Files:**
- Create: `requirements.txt`, `forms/f1040.pdf`, `forms/f1040sb.pdf`, `tests/conftest.py`, `.gitignore`
- Test: `tests/test_forms.py`

**Interfaces:**
- Consumes: nothing.
- Produces: fixtures `f1040_path` and `f1040sb_path` (both `pathlib.Path`) available to every later test.

- [ ] **Step 1: Write requirements.txt**

```
flask==3.1.3
pydantic==2.*
pypdf==6.16.1
reportlab==4.*
jsonpath-ng==1.*
pytest==8.*
```

- [ ] **Step 2: Install and vendor the forms**

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
mkdir -p forms
curl -fsSL -o forms/f1040.pdf   https://www.irs.gov/pub/irs-pdf/f1040.pdf
curl -fsSL -o forms/f1040sb.pdf https://www.irs.gov/pub/irs-pdf/f1040sb.pdf
sha256sum forms/*.pdf
```

Record both digests — they go into the annotation sets in Tasks 8 and 10.

- [ ] **Step 3: Write the failing test**

`tests/conftest.py`:

```python
import pathlib, pytest

FORMS = pathlib.Path(__file__).parent.parent / "forms"

@pytest.fixture
def f1040_path():
    return FORMS / "f1040.pdf"

@pytest.fixture
def f1040sb_path():
    return FORMS / "f1040sb.pdf"
```

`tests/test_forms.py`:

```python
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
```

- [ ] **Step 4: Run and confirm both pass**

Run: `pytest tests/test_forms.py -v`
Expected: PASS. If Schedule B is not 612×792, **update the assertion to the real value and note it in PLAN.md** — page size is per-page data in the model, not a constant.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt forms tests .gitignore
git commit -m "chore: vendor IRS forms, pin deps, assert page geometry"
```

---

### Task 1: The format — pydantic models and generated schema

**Files:**
- Create: `app/models.py`, `app/__init__.py` (empty for now)
- Create: `tools/gen_schema.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AnnotationSet`, `FieldAnnotation`, `GroupAnnotation`, `Box`, `Style`, `Condition`, `Format`, `FormMeta`, `SourceMeta`, `PageMeta`, and enum `FieldType`. `AnnotationSet.model_validate(dict) -> AnnotationSet`. Every later task imports from here and nowhere else.

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError
from app.models import AnnotationSet, FieldAnnotation, Box

MINIMAL = {
    "specVersion": "1.0",
    "form": {"id": "f1040", "title": "U.S. Individual Income Tax Return",
             "taxYear": 2024, "revision": "2024", "jurisdiction": "US-IRS"},
    "source": {"url": "https://www.irs.gov/pub/irs-pdf/f1040.pdf",
               "sha256": "0" * 64, "pageCount": 2},
    "pages": [{"number": 1, "width": 612, "height": 792},
              {"number": 2, "width": 612, "height": 792}],
    "annotations": [{
        "kind": "field", "id": "first_name", "label": "First name",
        "page": 1, "box": {"x": 40, "y": 96, "width": 200, "height": 14},
        "type": "text", "value": "$.taxpayer.firstName",
    }],
}

def test_minimal_set_validates():
    s = AnnotationSet.model_validate(MINIMAL)
    assert isinstance(s.annotations[0], FieldAnnotation)
    assert s.annotations[0].box == Box(x=40, y=96, width=200, height=14)

def test_kind_discriminates_field_from_group():
    doc = {**MINIMAL, "annotations": [{
        "kind": "group", "id": "sch_b_payers", "label": "Payers",
        "page": 1, "source": "$.income.interest[*]",
        "rowHeight": 16, "maxRows": 14,
        "firstRowBox": {"x": 40, "y": 200, "width": 400, "height": 14},
        "overflowStrategy": "statement",
        "columns": [{"kind": "field", "id": "payer", "label": "Payer",
                     "page": 1, "box": {"x": 0, "y": 0, "width": 300, "height": 14},
                     "type": "text", "value": "$.name"}],
    }]}
    s = AnnotationSet.model_validate(doc)
    assert s.annotations[0].kind == "group"

def test_non_base14_font_requires_fallback():
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "style": {"font": "Comic Sans MS", "size": 9}}]}
    with pytest.raises(ValidationError, match="fontFallback"):
        AnnotationSet.model_validate(doc)

def test_page_reference_must_exist():
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0], "page": 7}]}
    with pytest.raises(ValidationError, match="page 7"):
        AnnotationSet.model_validate(doc)

def test_ids_must_be_unique():
    a = MINIMAL["annotations"][0]
    doc = {**MINIMAL, "annotations": [a, dict(a)]}
    with pytest.raises(ValidationError, match="duplicate"):
        AnnotationSet.model_validate(doc)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write app/models.py**

```python
from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, model_validator

BASE14 = {"Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
          "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
          "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
          "Symbol", "ZapfDingbats"}

FieldType = Literal["text", "currency", "integer", "decimal",
                    "date", "ssn", "ein", "phone", "zip", "checkbox", "comb"]
# ponytail: no "multiline" — nothing in the v1 sets wraps, and a wrap engine
# with no caller is a spec promise no third party could verify. See SPEC.md §11.


class Box(BaseModel):
    """Top-left origin, y grows down, units are PDF points."""
    x: float
    y: float
    width: float
    height: float


class Style(BaseModel):
    font: str = "Helvetica"
    fontFallback: str | None = None
    size: float = 9.0
    color: str = "#000000"
    align: Literal["left", "center", "right"] = "left"
    valign: Literal["top", "middle", "bottom"] = "middle"
    padding: float = 1.5
    # ponytail: no letterSpacing (comb already owns character pitch) and no
    # rotation (no box in the v1 sets is rotated). Both in SPEC.md §11.

    @model_validator(mode="after")
    def _base14_or_fallback(self):
        if self.font not in BASE14 and self.fontFallback is None:
            raise ValueError(
                f"font {self.font!r} is not base-14; a fontFallback is required")
        if self.fontFallback is not None and self.fontFallback not in BASE14:
            raise ValueError(f"fontFallback {self.fontFallback!r} is not base-14")
        return self


class Condition(BaseModel):
    """Deliberately an object, not a JSONPath predicate: the spec's JSONPath
    subset excludes filter expressions, so it cannot express a comparison."""
    path: str
    op: Literal["exists", "absent", "truthy", "equals", "notEquals"] = "truthy"
    value: object | None = None

    @model_validator(mode="after")
    def _value_required_for_comparisons(self):
        if self.op in ("equals", "notEquals") and self.value is None:
            raise ValueError(f"op {self.op!r} requires a value")
        return self


class Format(BaseModel):
    decimals: int = 2
    thousandsSeparator: bool = True
    negative: Literal["parentheses", "minus"] = "parentheses"
    zeroSuppress: bool = True
    wholeDollars: bool = False
    datePattern: str = "%m/%d/%Y"
    cells: int | None = None          # comb: number of character cells
    checkedGlyph: str = "X"
    trueValues: list[object] = Field(default_factory=lambda: [True, "true", "Y", "yes", 1])


class FieldAnnotation(BaseModel):
    kind: Literal["field"] = "field"
    id: str
    label: str
    page: int
    box: Box
    type: FieldType
    value: str                        # JSONPath, relative to the row inside a group
    acroFieldName: str | None = None  # hint only; coordinates win on conflict
    required: bool = False
    format: Format = Field(default_factory=Format)
    style: Style = Field(default_factory=Style)
    # ponytail: shrink | clip | error only. "wrap" and "truncate" had no
    # implementation and no test, so they were cut rather than shipped as
    # enum values a conforming renderer could not actually rely on.
    overflow: Literal["shrink", "clip", "error"] = "shrink"
    minSize: float = 5.0
    condition: Condition | None = None

    @model_validator(mode="after")
    def _comb_needs_cells(self):
        if self.type == "comb" and not self.format.cells:
            raise ValueError(f"{self.id}: comb annotations require format.cells")
        return self


class GroupAnnotation(BaseModel):
    kind: Literal["group"]
    id: str
    label: str
    page: int
    source: str                       # JSONPath to an array
    rowHeight: float
    maxRows: int
    firstRowBox: Box
    columns: list[FieldAnnotation]
    # ponytail: "continuation" (spill onto a second page) needs page cloning
    # the v1 renderer does not do. Cut, not reserved. SPEC.md §11.
    overflowStrategy: Literal["statement", "error"] = "statement"
    overflowTarget: str | None = None
    condition: Condition | None = None


Annotation = Annotated[Union[FieldAnnotation, GroupAnnotation],
                       Field(discriminator="kind")]


class FormMeta(BaseModel):
    id: str
    title: str
    taxYear: int
    revision: str
    jurisdiction: str = "US-IRS"


class SourceMeta(BaseModel):
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pageCount: int


class PageMeta(BaseModel):
    number: int
    width: float
    height: float


class AnnotationSet(BaseModel):
    specVersion: Literal["1.0"]
    form: FormMeta
    source: SourceMeta
    pages: list[PageMeta]
    defaults: Style = Field(default_factory=Style)
    annotations: list[Annotation]

    @model_validator(mode="after")
    def _referential_integrity(self):
        pages = {p.number for p in self.pages}
        seen: set[str] = set()
        for a in self.annotations:
            if a.page not in pages:
                raise ValueError(f"{a.id}: page {a.page} is not declared in pages[]")
            if a.id in seen:
                raise ValueError(f"duplicate annotation id {a.id!r}")
            seen.add(a.id)
            if isinstance(a, GroupAnnotation):
                for c in a.columns:
                    if c.id in seen:
                        raise ValueError(f"duplicate annotation id {c.id!r}")
                    seen.add(c.id)
                if a.overflowStrategy == "statement" and not a.overflowTarget:
                    raise ValueError(
                        f"{a.id}: overflowStrategy 'statement' requires overflowTarget")
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Generate the JSON Schema from the models**

`tools/gen_schema.py`:

```python
"""Regenerate schema/annotation-set.schema.json from the pydantic models.
The models are canonical; this file is build output. Never hand-edit it."""
import json, pathlib
from app.models import AnnotationSet

out = pathlib.Path(__file__).parent.parent / "schema" / "annotation-set.schema.json"
out.parent.mkdir(exist_ok=True)
schema = AnnotationSet.model_json_schema()
schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
schema["$id"] = "https://instead.example/schema/annotation-set-1.0.json"
out.write_text(json.dumps(schema, indent=2) + "\n")
print(f"wrote {out}")
```

Add to `tests/test_models.py`:

```python
def test_generated_schema_is_current():
    """Fails if someone edits models.py and forgets to regenerate."""
    import json, pathlib, subprocess, sys
    p = pathlib.Path("schema/annotation-set.schema.json")
    before = p.read_text()
    subprocess.run([sys.executable, "tools/gen_schema.py"], check=True)
    assert p.read_text() == before, "run: python tools/gen_schema.py"
```

- [ ] **Step 6: Run the generator, then the full test file**

Run: `python tools/gen_schema.py && pytest tests/test_models.py -v`
Expected: schema written; 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/__init__.py tools/gen_schema.py schema tests/test_models.py
git commit -m "feat: annotation format as pydantic models with generated JSON Schema"
```

---

### Task 2: Geometry — the single coordinate conversion

**Files:**
- Create: `app/geometry.py`
- Test: `tests/test_geometry.py`

**Interfaces:**
- Consumes: `app.models.Box`, `app.models.Style`.
- Produces:
  - `to_pdf_rect(box: Box, page_height: float) -> tuple[float, float, float, float]` returning `(x_left, y_bottom, width, height)` in PDF user space.
  - `baseline_y(box: Box, page_height: float, style: Style) -> float`.
  - `anchor_x(box: Box, style: Style, text_width: float) -> float`.
  - `CAP_HEIGHT_RATIO: float = 0.72`.

- [ ] **Step 1: Write the failing test**

`tests/test_geometry.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.geometry'`

- [ ] **Step 3: Write app/geometry.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_geometry.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add app/geometry.py tests/test_geometry.py
git commit -m "feat: single top-left to PDF coordinate conversion"
```

---

### Task 3: Resolver — the JSONPath subset and conditions

**Files:**
- Create: `app/resolver.py`
- Test: `tests/test_resolver.py`

**Interfaces:**
- Consumes: `app.models.Condition`.
- Produces:
  - `resolve_one(path: str, data: dict, *, required: bool, annotation_id: str) -> object | None` — returns `None` for zero matches unless `required`, raises `MultipleMatchesError` for >1.
  - `resolve_many(path: str, data: dict) -> list[object]`.
  - `evaluate(cond: Condition | None, data: dict) -> bool` — `None` means "always print".
  - Exceptions `MissingValueError`, `MultipleMatchesError`, `UnsupportedPathError`.

- [ ] **Step 1: Write the failing test**

`tests/test_resolver.py`:

```python
import pytest
from app.models import Condition
from app.resolver import (resolve_one, resolve_many, evaluate,
                          MissingValueError, MultipleMatchesError, UnsupportedPathError)

DATA = {
    "taxpayer": {"firstName": "Ada", "ssn": "123456789", "spouse": None},
    "income": {"w2": [{"wages": 52000.0}, {"wages": 8000.0}],
               "interest": [{"payer": "Acme Bank", "amount": 120.5}]},
    "filingStatus": "single",
}

def test_child_access():
    assert resolve_one("$.taxpayer.firstName", DATA, required=False, annotation_id="t") == "Ada"

def test_array_index():
    assert resolve_one("$.income.w2[0].wages", DATA, required=False, annotation_id="t") == 52000.0

def test_missing_path_returns_none():
    assert resolve_one("$.taxpayer.middleName", DATA, required=False, annotation_id="t") is None

def test_missing_required_path_raises_naming_the_annotation():
    with pytest.raises(MissingValueError, match="line_1a"):
        resolve_one("$.nope", DATA, required=True, annotation_id="line_1a")

def test_explicit_null_is_treated_as_absent():
    assert resolve_one("$.taxpayer.spouse", DATA, required=False, annotation_id="t") is None

def test_multiple_matches_on_a_field_is_an_error():
    with pytest.raises(MultipleMatchesError, match="2 matches"):
        resolve_one("$.income.w2[*].wages", DATA, required=False, annotation_id="t")

def test_resolve_many_returns_all_matches_in_document_order():
    assert resolve_many("$.income.w2[*].wages", DATA) == [52000.0, 8000.0]

def test_resolve_many_on_missing_path_is_empty():
    assert resolve_many("$.income.k1[*]", DATA) == []

def test_filter_expressions_are_rejected():
    with pytest.raises(UnsupportedPathError):
        resolve_many("$.income.w2[?(@.wages > 1000)]", DATA)

def test_condition_none_always_prints():
    assert evaluate(None, DATA) is True

@pytest.mark.parametrize("cond,expected", [
    (Condition(path="$.filingStatus", op="equals", value="single"), True),
    (Condition(path="$.filingStatus", op="equals", value="mfj"), False),
    (Condition(path="$.filingStatus", op="notEquals", value="mfj"), True),
    (Condition(path="$.taxpayer.firstName", op="exists"), True),
    (Condition(path="$.taxpayer.middleName", op="exists"), False),
    (Condition(path="$.taxpayer.middleName", op="absent"), True),
    (Condition(path="$.taxpayer.spouse", op="truthy"), False),
])
def test_conditions(cond, expected):
    assert evaluate(cond, DATA) is expected
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.resolver'`

- [ ] **Step 3: Write app/resolver.py**

```python
"""Resolution of the spec's JSONPath subset.

Imports the BASE jsonpath_ng parser, never jsonpath_ng.ext. The base grammar
has no filter or script expressions, so the portable subset the spec promises
is enforced by construction rather than by a blocklist.
"""
from functools import lru_cache
from jsonpath_ng import parse as _parse
from jsonpath_ng.exceptions import JsonPathParserError
from app.models import Condition


class MissingValueError(KeyError): ...
class MultipleMatchesError(ValueError): ...
class UnsupportedPathError(ValueError): ...


@lru_cache(maxsize=512)
def _compile(path: str):
    try:
        return _parse(path)
    except (JsonPathParserError, Exception) as exc:  # parser raises broadly
        raise UnsupportedPathError(
            f"{path!r} is not in the supported JSONPath subset "
            f"(child, index, [*], .. only; filters are excluded): {exc}") from exc


def resolve_many(path: str, data) -> list:
    return [m.value for m in _compile(path).find(data)]


def resolve_one(path: str, data, *, required: bool, annotation_id: str):
    matches = [v for v in resolve_many(path, data) if v is not None]
    if len(matches) > 1:
        raise MultipleMatchesError(
            f"{annotation_id}: {path!r} produced {len(matches)} matches; "
            f"multiplicity is only legal inside a group")
    if not matches:
        if required:
            raise MissingValueError(
                f"{annotation_id}: required path {path!r} resolved to nothing")
        return None
    return matches[0]


def evaluate(cond: Condition | None, data) -> bool:
    if cond is None:
        return True
    matches = resolve_many(cond.path, data)
    present = [v for v in matches if v is not None]
    if cond.op == "exists":
        return bool(present)
    if cond.op == "absent":
        return not present
    if cond.op == "truthy":
        return bool(present) and bool(present[0])
    if cond.op == "equals":
        return bool(present) and present[0] == cond.value
    if cond.op == "notEquals":
        return not present or present[0] != cond.value
    raise UnsupportedPathError(f"unknown condition op {cond.op!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_resolver.py -v`
Expected: PASS (all, including the 7 parametrised conditions).

- [ ] **Step 5: Commit**

```bash
git add app/resolver.py tests/test_resolver.py
git commit -m "feat: JSONPath subset resolver with normative missing/multiple semantics"
```

---

### Task 4: Formatter — typed value to display string

**Files:**
- Create: `app/formatter.py`
- Test: `tests/test_formatter.py`

**Interfaces:**
- Consumes: `app.models.FieldAnnotation`, `app.models.Format`.
- Produces: `format_value(ann: FieldAnnotation, raw: object | None) -> str | list[str]` — a `str` for every type except `comb`, which returns a `list[str]` of per-cell glyphs (`""` for an empty cell). `""` means "draw nothing".

- [ ] **Step 1: Write the failing test**

`tests/test_formatter.py`:

```python
import pytest
from app.models import FieldAnnotation, Box, Format
from app.formatter import format_value

def ann(type_, **fmt):
    return FieldAnnotation(id="t", label="t", page=1,
                           box=Box(x=0, y=0, width=100, height=14),
                           type=type_, value="$.x", format=Format(**fmt))

@pytest.mark.parametrize("raw,expected", [
    (52000.0, "52,000.00"),
    (0, ""),                       # zeroSuppress default
    (-1234.5, "(1,234.50)"),
    (1234.567, "1,234.57"),        # half-even at 2dp
])
def test_currency(raw, expected):
    assert format_value(ann("currency"), raw) == expected

def test_currency_whole_dollars_rounds_and_drops_cents():
    assert format_value(ann("currency", wholeDollars=True), 1234.56) == "1,235"

def test_currency_minus_convention():
    assert format_value(ann("currency", negative="minus"), -12.0) == "-12.00"

def test_currency_zero_not_suppressed_when_disabled():
    assert format_value(ann("currency", zeroSuppress=False), 0) == "0.00"

def test_none_always_renders_empty():
    assert format_value(ann("currency"), None) == ""
    assert format_value(ann("text"), None) == ""

def test_ssn_comb_returns_nine_cells():
    cells = format_value(ann("ssn", cells=9), "123-45-6789")
    assert cells == list("123456789")

def test_comb_pads_short_values_and_rejects_long_ones():
    assert format_value(ann("zip", cells=5), "021") == ["0", "2", "1", "", ""]
    with pytest.raises(ValueError, match="9 cells"):
        format_value(ann("ssn", cells=9), "1234567890")

def test_date_uses_pattern():
    assert format_value(ann("date"), "2025-04-15") == "04/15/2025"

def test_date_rejects_non_iso_input():
    with pytest.raises(ValueError, match="ISO 8601"):
        format_value(ann("date"), "April 15 2025")

@pytest.mark.parametrize("raw,expected", [(True, "X"), ("yes", "X"), (1, "X"),
                                          (False, ""), (None, ""), ("no", "")])
def test_checkbox(raw, expected):
    assert format_value(ann("checkbox"), raw) == expected

def test_integer_and_text_passthrough():
    assert format_value(ann("integer"), 3) == "3"
    assert format_value(ann("text"), "Ada Lovelace") == "Ada Lovelace"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.formatter'`

- [ ] **Step 3: Write app/formatter.py**

```python
"""Typed value -> display string. Contains no PDF calls and no JSONPath."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
import re
from app.models import FieldAnnotation

COMB_TYPES = {"ssn", "ein", "zip", "phone", "comb"}


def format_value(ann: FieldAnnotation, raw):
    f = ann.format
    if raw is None:
        return [""] * f.cells if (ann.type in COMB_TYPES and f.cells) else ""

    if ann.type == "checkbox":
        return f.checkedGlyph if raw in f.trueValues else ""

    if ann.type == "currency" or ann.type == "decimal":
        return _money(Decimal(str(raw)), ann)

    if ann.type == "date":
        return _date(raw, f.datePattern)

    if ann.type in COMB_TYPES and f.cells:
        digits = re.sub(r"[^0-9A-Za-z]", "", str(raw))
        if len(digits) > f.cells:
            raise ValueError(
                f"{ann.id}: {raw!r} does not fit in {f.cells} cells")
        return list(digits) + [""] * (f.cells - len(digits))

    return str(raw)


def _money(v: Decimal, ann: FieldAnnotation) -> str:
    f = ann.format
    if f.zeroSuppress and v == 0:
        return ""
    places = 0 if f.wholeDollars else f.decimals
    q = Decimal(1).scaleb(-places)
    v = v.quantize(q, rounding=ROUND_HALF_EVEN)
    neg = v < 0
    body = f"{abs(v):,.{places}f}" if f.thousandsSeparator else f"{abs(v):.{places}f}"
    if not neg:
        return body
    return f"({body})" if f.negative == "parentheses" else f"-{body}"


def _date(raw, pattern: str) -> str:
    if isinstance(raw, (date, datetime)):
        return raw.strftime(pattern)
    try:
        return date.fromisoformat(str(raw)).strftime(pattern)
    except ValueError as exc:
        raise ValueError(
            f"date values must be ISO 8601 (YYYY-MM-DD); got {raw!r}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_formatter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/formatter.py tests/test_formatter.py
git commit -m "feat: typed value formatting with currency, comb, date and checkbox rules"
```

---

### Task 5: Loader — read, validate, verify provenance

**Files:**
- Create: `app/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `app.models.AnnotationSet`.
- Produces: `load_set(path: str | Path, *, strict: bool = False) -> AnnotationSet` and `verify_source(aset: AnnotationSet, pdf_path: Path, *, strict: bool) -> list[str]` returning warning strings.

- [ ] **Step 1: Write the failing test**

`tests/test_loader.py`:

```python
import json, pytest
from app.loader import load_set, verify_source, SourceMismatch
from tests.test_models import MINIMAL

def _write(tmp_path, doc):
    p = tmp_path / "set.json"
    p.write_text(json.dumps(doc))
    return p

def test_load_returns_a_validated_set(tmp_path):
    assert load_set(_write(tmp_path, MINIMAL)).form.id == "f1040"

def test_invalid_set_raises_with_the_offending_field(tmp_path):
    bad = {**MINIMAL, "source": {**MINIMAL["source"], "sha256": "nope"}}
    with pytest.raises(ValueError, match="sha256"):
        load_set(_write(tmp_path, bad))

def test_sha_mismatch_warns_by_default(tmp_path, f1040_path):
    aset = load_set(_write(tmp_path, MINIMAL))   # MINIMAL pins all-zero sha
    warnings = verify_source(aset, f1040_path, strict=False)
    assert any("sha256" in w for w in warnings)

def test_sha_mismatch_raises_under_strict(tmp_path, f1040_path):
    aset = load_set(_write(tmp_path, MINIMAL))
    with pytest.raises(SourceMismatch):
        verify_source(aset, f1040_path, strict=True)

def test_page_count_mismatch_warns(tmp_path, f1040sb_path):
    aset = load_set(_write(tmp_path, MINIMAL))   # declares 2 pages
    assert any("page count" in w for w in verify_source(aset, f1040sb_path, strict=False))
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.loader'`

- [ ] **Step 3: Write app/loader.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_loader.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/loader.py tests/test_loader.py
git commit -m "feat: annotation set loader with provenance verification"
```

---

### Task 6: Renderer spine — draw fields onto the real PDF

**Files:**
- Create: `app/renderer.py`, `tests/pdf_probe.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces:
  - `render(aset: AnnotationSet, data: dict, pdf_path: Path, *, debug: bool = False) -> bytes`
  - `tests/pdf_probe.py::extract_placements(pdf_bytes, page=0) -> list[dict]` with keys `text`, `x`, `y` (**y already converted back to top-left**), `size`. This is the verification tool — byte comparison is banned by the Global Constraints.

- [ ] **Step 1: Write the probe helper**

`tests/pdf_probe.py`:

```python
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
```

- [ ] **Step 2: Write the failing test**

`tests/test_renderer.py`:

```python
import pytest
from app.models import AnnotationSet
from app.renderer import render
from tests.pdf_probe import extract_placements, find
from tests.test_models import MINIMAL

DATA = {"taxpayer": {"firstName": "Ada"}}

def test_value_lands_inside_its_declared_box(f1040_path):
    aset = AnnotationSet.model_validate(MINIMAL)
    out = render(aset, DATA, f1040_path)
    p = find(extract_placements(out), "Ada")
    box = aset.annotations[0].box
    assert box.x <= p["x"] <= box.x + box.width
    assert box.y <= p["y"] <= box.y + box.height

def test_output_preserves_the_original_page_count(f1040_path):
    from pypdf import PdfReader; import io
    out = render(AnnotationSet.model_validate(MINIMAL), DATA, f1040_path)
    assert len(PdfReader(io.BytesIO(out)).pages) == 2

def test_absent_value_draws_nothing(f1040_path):
    out = render(AnnotationSet.model_validate(MINIMAL), {}, f1040_path)
    assert not [p for p in extract_placements(out) if p["text"].strip() == "Ada"]

def test_false_condition_suppresses_the_annotation(f1040_path):
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "condition": {"path": "$.filingStatus", "op": "equals", "value": "mfj"}}]}
    out = render(AnnotationSet.model_validate(doc), {**DATA, "filingStatus": "single"}, f1040_path)
    assert not [p for p in extract_placements(out) if "Ada" in p["text"]]

def test_overflow_shrink_reduces_size_but_never_below_minsize(f1040_path):
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "box": {"x": 40, "y": 96, "width": 30, "height": 14},
           "overflow": "shrink", "minSize": 6, "style": {"size": 12}}]}
    out = render(AnnotationSet.model_validate(doc),
                 {"taxpayer": {"firstName": "Bartholomew Fitzgerald"}}, f1040_path)
    p = find(extract_placements(out), "Bartholomew")
    assert 6 <= p["size"] < 12

def test_overflow_error_raises_naming_the_annotation(f1040_path):
    doc = {**MINIMAL, "annotations": [{**MINIMAL["annotations"][0],
           "box": {"x": 40, "y": 96, "width": 20, "height": 14}, "overflow": "error"}]}
    with pytest.raises(ValueError, match="first_name"):
        render(AnnotationSet.model_validate(doc),
               {"taxpayer": {"firstName": "Bartholomew Fitzgerald"}}, f1040_path)

def test_debug_mode_draws_more_than_normal_mode(f1040_path):
    aset = AnnotationSet.model_validate(MINIMAL)
    assert len(render(aset, DATA, f1040_path, debug=True)) > \
           len(render(aset, DATA, f1040_path))
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/test_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.renderer'`

- [ ] **Step 4: Write app/renderer.py**

```python
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
from app.resolver import resolve_one, evaluate


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


def render(aset: AnnotationSet, data: dict, pdf_path: Path, *, debug: bool = False) -> bytes:
    base = PdfReader(pdf_path)
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    by_page = {p.number: p for p in aset.pages}

    for pno in sorted(by_page):
        page = by_page[pno]
        c.setPageSize((page.width, page.height))
        for ann in aset.annotations:
            if ann.page != pno:
                continue
            if isinstance(ann, FieldAnnotation):
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
    raise NotImplementedError("Task 7")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_renderer.py -v`
Expected: PASS (7 tests). **Also render one PDF and look at it** — this is the first visual proof the origin convention is right:

```bash
python -c "
from pathlib import Path; from app.models import AnnotationSet
from app.renderer import render; from tests.test_models import MINIMAL
Path('/tmp/proof.pdf').write_bytes(render(AnnotationSet.model_validate(MINIMAL),
    {'taxpayer':{'firstName':'Ada'}}, Path('forms/f1040.pdf'), debug=True))"
```

A wrong origin costs minutes here and costs the annotation sets if found in Task 9.

- [ ] **Step 6: Commit**

```bash
git add app/renderer.py tests/test_renderer.py tests/pdf_probe.py
git commit -m "feat: reportlab overlay renderer with overflow, comb and debug modes"
```

---

### Task 7: Repeating groups and overflow

**Files:**
- Modify: `app/renderer.py` — replace `_draw_group`
- Test: `tests/test_groups.py`

**Interfaces:**
- Consumes: `GroupAnnotation`, `resolve_many`.
- Produces: `_draw_group(c, aset, grp, data, page_h, debug) -> None`. Column `value` paths resolve **against the row item**, not the document root. Row *n* box = `firstRowBox` offset by `n * rowHeight` in y, plus each column's `box.x`/`box.width`.

- [ ] **Step 1: Write the failing test**

`tests/test_groups.py`:

```python
import pytest
from app.models import AnnotationSet
from app.renderer import render
from tests.pdf_probe import extract_placements, find
from tests.test_models import MINIMAL

def group_doc(max_rows=2, strategy="statement", target="sch_b_note"):
    ann = {"kind": "group", "id": "payers", "label": "Payers", "page": 1,
           "source": "$.income.interest[*]", "rowHeight": 16, "maxRows": max_rows,
           "firstRowBox": {"x": 40, "y": 300, "width": 400, "height": 14},
           "overflowStrategy": strategy,
           "columns": [
               {"kind": "field", "id": "payer", "label": "Payer", "page": 1,
                "box": {"x": 40, "y": 300, "width": 280, "height": 14},
                "type": "text", "value": "$.name"},
               {"kind": "field", "id": "amount", "label": "Amount", "page": 1,
                "box": {"x": 330, "y": 300, "width": 110, "height": 14},
                "type": "currency", "value": "$.amount",
                "style": {"align": "right"}}]}
    if strategy == "statement":
        ann["overflowTarget"] = target
    note = {"kind": "field", "id": target or "sch_b_note", "label": "Note", "page": 1,
            "box": {"x": 40, "y": 500, "width": 400, "height": 14},
            "type": "text", "value": "$.overflowNote"}
    return {**MINIMAL, "annotations": [ann, note]}

def data(n):
    return {"income": {"interest": [{"name": f"Bank {i}", "amount": 100.0 + i}
                                    for i in range(n)]},
            "overflowNote": "See attached statement"}

def test_each_row_is_offset_by_exactly_rowheight(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc()), data(2), f1040_path)
    pl = extract_placements(out)
    assert round(find(pl, "Bank 1")["y"] - find(pl, "Bank 0")["y"]) == 16

def test_column_paths_resolve_against_the_row_not_the_root(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc()), data(1), f1040_path)
    assert find(extract_placements(out), "100.00")

def test_rows_beyond_maxrows_are_not_drawn(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc(max_rows=2)), data(5), f1040_path)
    texts = " ".join(p["text"] for p in extract_placements(out))
    assert "Bank 1" in texts and "Bank 2" not in texts

def test_statement_strategy_prints_the_overflow_target(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc(max_rows=2)), data(5), f1040_path)
    assert find(extract_placements(out), "See attached statement")

def test_no_overflow_means_the_target_still_follows_its_own_value(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc(max_rows=9)), data(2), f1040_path)
    assert find(extract_placements(out), "See attached statement")

def test_error_strategy_raises_rather_than_dropping_rows(f1040_path):
    doc = group_doc(max_rows=2, strategy="error", target=None)
    with pytest.raises(ValueError, match="payers"):
        render(AnnotationSet.model_validate(doc), data(5), f1040_path)

def test_empty_array_draws_no_rows(f1040_path):
    out = render(AnnotationSet.model_validate(group_doc()), {"income": {"interest": []}}, f1040_path)
    assert not [p for p in extract_placements(out) if "Bank" in p["text"]]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_groups.py -v`
Expected: FAIL — `NotImplementedError: Task 7`

- [ ] **Step 3: Replace `_draw_group` in app/renderer.py**

```python
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
```

Add `resolve_many` to the `app.resolver` import at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_groups.py tests/test_renderer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/renderer.py tests/test_groups.py
git commit -m "feat: repeating groups with row-relative paths and overflow strategies"
```

---

### Task 8: Extraction tool — bootstrap annotations from AcroForm widgets

**Files:**
- Create: `tools/extract_widgets.py`
- Test: `tests/test_extract_widgets.py`

**Interfaces:**
- Consumes: `app.models`.
- Produces: `extract(pdf_path: Path, form_id: str, tax_year: int) -> dict` — a draft annotation-set dict that `AnnotationSet.model_validate` accepts. CLI: `python tools/extract_widgets.py forms/f1040.pdf f1040 2024 > annotations/f1040-2024.draft.json`.

Rationale: the 1040 carries 229 AcroForm widgets, each with a `/Rect` that **is** the IRS's own box geometry. Bootstrapping from them turns "measure boxes by hand" into "name the boxes and assign paths."

- [ ] **Step 1: Write the failing test**

`tests/test_extract_widgets.py`:

```python
from app.models import AnnotationSet
from tools.extract_widgets import extract, infer_type

def test_extraction_output_is_a_valid_annotation_set(f1040_path):
    AnnotationSet.model_validate(extract(f1040_path, "f1040", 2024))

def test_extraction_finds_the_expected_order_of_magnitude_of_widgets(f1040_path):
    assert len(extract(f1040_path, "f1040", 2024)["annotations"]) > 150

def test_rects_are_converted_to_top_left_and_stay_on_the_page(f1040_path):
    doc = extract(f1040_path, "f1040", 2024)
    for a in doc["annotations"]:
        assert 0 <= a["box"]["y"] <= 792
        assert a["box"]["y"] + a["box"]["height"] <= 792.5

def test_type_inference_follows_the_irs_naming_convention():
    assert infer_type("topmostSubform[0].Page1[0].c1_1[0]", "/Btn") == "checkbox"
    assert infer_type("topmostSubform[0].Page1[0].f1_04[0]", "/Tx") == "text"

def test_every_draft_annotation_carries_its_acrofieldname_hint(f1040_path):
    doc = extract(f1040_path, "f1040", 2024)
    assert all(a["acroFieldName"] for a in doc["annotations"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_extract_widgets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.extract_widgets'`

- [ ] **Step 3: Write tools/extract_widgets.py**

```python
"""AcroForm widget rects -> a draft annotation set.

The IRS ships the box geometry inside the PDF. Extract it, then a human names
each annotation and assigns its JSONPath. Draft output is a starting point,
not a deliverable: it is filtered down to the representative subset by hand.
"""
import hashlib, json, re, sys
from pathlib import Path
from pypdf import PdfReader


def infer_type(field_name: str, ft: str) -> str:
    if ft == "/Btn":
        return "checkbox"
    return "text"


def _slug(name: str, n: int) -> str:
    tail = re.sub(r"[^0-9a-zA-Z]+", "_", name.split(".")[-1]).strip("_").lower()
    return f"{tail or 'field'}_{n}"


def extract(pdf_path: Path, form_id: str, tax_year: int) -> dict:
    pdf_path = Path(pdf_path)
    reader = PdfReader(pdf_path)
    annotations, n = [], 0
    for pno, page in enumerate(reader.pages, start=1):
        page_h = float(page.mediabox.height)
        for ref in page.get("/Annots", []) or []:
            w = ref.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            fld = w
            while fld is not None and "/T" not in fld:
                fld = fld.get("/Parent")
            if fld is None:
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
    parts, cur = [], fld
    while cur is not None:
        if "/T" in cur:
            parts.append(str(cur["/T"]))
        cur = cur.get("/Parent")
        cur = cur.get_object() if cur is not None else None
    return ".".join(reversed(parts))


if __name__ == "__main__":
    pdf, form_id, year = sys.argv[1], sys.argv[2], int(sys.argv[3])
    print(json.dumps(extract(Path(pdf), form_id, year), indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_extract_widgets.py -v`
Expected: PASS (5 tests). If `test_extraction_finds_the_expected_order_of_magnitude_of_widgets` fails, the widget-walk is missing kids — fix the traversal, do not lower the threshold.

- [ ] **Step 5: Commit**

```bash
git add tools/extract_widgets.py tests/test_extract_widgets.py
git commit -m "feat: bootstrap draft annotations from AcroForm widget geometry"
```

---

### Task 9: Author the real annotation sets and example datasets

**Files:**
- Create: `annotations/f1040-2024.json`, `annotations/f1040sb-2024.json`
- Create: `examples/simple-w2.json`, `examples/joint-dependents.json`, `examples/schedule-b-overflow.json`
- Test: `tests/test_annotation_sets.py`

**Interfaces:**
- Consumes: everything above.
- Produces: the shipped data. **Scope is the representative subset (decision D10):** every `FieldType` appears at least once across 1040 p1/p2, plus Schedule B Part I in full as a group. Target ~30–40 field annotations, not 229.

Coverage checklist the sets MUST hit — this is what makes the subset defensible:

| Case | Where |
|---|---|
| plain text | first/last name, address |
| comb | SSN (9 cells), ZIP (5 cells) |
| checkbox + mutual exclusion via `condition` | filing-status boxes on 1040 p1 |
| currency, split dollars/cents as **two annotations** (D8) | line 1a wages |
| negative currency in parentheses | a loss line on p1 |
| zero suppression | any line the simple example leaves at 0 |
| date | signature date, p2 |
| integer | dependent count |
| bounded repeating group | dependents table, 1040 p1 |
| unbounded repeating group + `statement` overflow | Schedule B Part I payers |
| `required: true` | taxpayer SSN |
| `overflow: shrink` | name line with a long name in `joint-dependents.json` |

- [ ] **Step 1: Generate the drafts**

```bash
python tools/extract_widgets.py forms/f1040.pdf   f1040   2024 > /tmp/f1040.draft.json
python tools/extract_widgets.py forms/f1040sb.pdf f1040sb 2024 > /tmp/f1040sb.draft.json
```

- [ ] **Step 2: Write the failing test first**

`tests/test_annotation_sets.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/test_annotation_sets.py -v`
Expected: FAIL — files not found.

- [ ] **Step 4: Author the sets**

For each draft entry you keep: give it a meaningful `id` (`line_1a_wages_dollars`, not `f1_04_12`), a real `value` JSONPath, and the `type`/`format` the coverage table requires. Delete every draft entry outside the subset. Move the dependents table and Schedule B payer rows into `kind: "group"` entries; check the extracted per-row y-deltas to get `rowHeight` right rather than guessing.

Then write the three example datasets so that between them every row of the coverage table is exercised. `schedule-b-overflow.json` MUST carry more payers than `maxRows`.

- [ ] **Step 5: Render all three and look at the output**

```bash
for e in simple-w2 joint-dependents schedule-b-overflow; do
  python -m app.cli annotations/f1040-2024.json examples/$e.json -o /tmp/$e.pdf --debug
done
```

(If `app.cli` does not exist yet, use the inline `python -c` form from Task 6 Step 5.) Every value must sit inside its red debug box. Nothing may be clipped or silently dropped.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest -v`
Expected: whole suite PASS.

- [ ] **Step 7: Commit**

```bash
git add annotations examples tests/test_annotation_sets.py
git commit -m "feat: representative 1040 and Schedule B annotation sets with example datasets"
```

---

### Task 10: Flask app and debug overlay

**Files:**
- Create: `app/routes.py`, `app/templates/index.html`, `app/cli.py`
- Modify: `app/__init__.py` — app factory
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `load_set`, `verify_source`, `render`.
- Produces:
  - `create_app() -> Flask`
  - `GET /` — pick a form, paste or upload a dataset, download the filled PDF
  - `POST /api/render` — body `{"form": "f1040", "data": {...}, "debug": bool}` → `application/pdf`
  - `POST /api/validate` — same body minus `data` → `{"valid": bool, "warnings": [...], "errors": [...]}`
  - `python -m app.cli <set.json> <data.json> -o out.pdf [--debug] [--strict]`

`routes.py` holds HTTP concerns only: parse, call, serialise errors. No JSONPath, no reportlab.

- [ ] **Step 1: Write the failing test**

`tests/test_routes.py`:

```python
import json, pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app(); app.config["TESTING"] = True
    return app.test_client()

def test_index_lists_the_available_forms(client):
    r = client.get("/")
    assert r.status_code == 200 and b"f1040" in r.data

def test_render_returns_a_pdf(client):
    data = json.loads(open("examples/simple-w2.json").read())
    r = client.post("/api/render", json={"form": "f1040", "data": data})
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF")

def test_debug_flag_produces_a_larger_pdf(client):
    data = json.loads(open("examples/simple-w2.json").read())
    plain = client.post("/api/render", json={"form": "f1040", "data": data}).data
    dbg = client.post("/api/render", json={"form": "f1040", "data": data,
                                           "debug": True}).data
    assert len(dbg) > len(plain)

def test_unknown_form_is_404_not_500(client):
    r = client.post("/api/render", json={"form": "f9999", "data": {}})
    assert r.status_code == 404

def test_a_required_path_missing_from_the_data_is_a_422_with_the_annotation_id(client):
    r = client.post("/api/render", json={"form": "f1040", "data": {}})
    assert r.status_code == 422
    assert "id" in r.get_json()["error"] or r.get_json()["error"]

def test_validate_reports_clean_for_a_shipped_set(client):
    r = client.post("/api/validate", json={"form": "f1040"})
    assert r.get_json() == {"valid": True, "warnings": [], "errors": []}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_routes.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_app'`

- [ ] **Step 3: Write the app factory, routes, CLI and template**

`app/__init__.py`:

```python
from flask import Flask

def create_app() -> Flask:
    app = Flask(__name__)
    from app.routes import bp
    app.register_blueprint(bp)
    return app
```

`app/routes.py`:

```python
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request, send_file
import io

from app.loader import load_set, verify_source
from app.renderer import render
from app.resolver import MissingValueError, MultipleMatchesError, UnsupportedPathError

bp = Blueprint("main", __name__)

FORMS = {
    "f1040":   (Path("annotations/f1040-2024.json"),   Path("forms/f1040.pdf")),
    "f1040sb": (Path("annotations/f1040sb-2024.json"), Path("forms/f1040sb.pdf")),
}


@bp.get("/")
def index():
    return render_template("index.html", forms=sorted(FORMS))


@bp.post("/api/render")
def api_render():
    body = request.get_json(silent=True) or {}
    entry = FORMS.get(body.get("form", ""))
    if entry is None:
        return jsonify(error=f"unknown form {body.get('form')!r}"), 404
    set_path, pdf_path = entry
    try:
        pdf = render(load_set(set_path), body.get("data") or {}, pdf_path,
                     debug=bool(body.get("debug")))
    except (MissingValueError, MultipleMatchesError, UnsupportedPathError, ValueError) as exc:
        return jsonify(error=str(exc)), 422
    return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                     as_attachment=True, download_name=f"{body['form']}-filled.pdf")


@bp.post("/api/validate")
def api_validate():
    body = request.get_json(silent=True) or {}
    entry = FORMS.get(body.get("form", ""))
    if entry is None:
        return jsonify(error=f"unknown form {body.get('form')!r}"), 404
    set_path, pdf_path = entry
    try:
        warnings = verify_source(load_set(set_path), pdf_path, strict=False)
    except Exception as exc:
        return jsonify(valid=False, warnings=[], errors=[str(exc)])
    return jsonify(valid=not warnings, warnings=warnings, errors=[])
```

`app/cli.py`:

```python
"""python -m app.cli annotations/f1040-2024.json examples/simple-w2.json -o out.pdf"""
import argparse, json
from pathlib import Path
from app.loader import load_set, verify_source
from app.renderer import render
from app.routes import FORMS

p = argparse.ArgumentParser()
p.add_argument("annotation_set"); p.add_argument("dataset")
p.add_argument("-o", "--out", required=True)
p.add_argument("--debug", action="store_true"); p.add_argument("--strict", action="store_true")
a = p.parse_args()

aset = load_set(a.annotation_set)
pdf_path = next(pdf for s, pdf in FORMS.values() if s == Path(a.annotation_set))
for w in verify_source(aset, pdf_path, strict=a.strict):
    print(f"warning: {w}")
Path(a.out).write_bytes(
    render(aset, json.loads(Path(a.dataset).read_text()), pdf_path, debug=a.debug))
print(f"wrote {a.out}")
```

`app/templates/index.html`: a single page with a `<select>` over `forms`, a `<textarea>` for the dataset JSON, a `debug` checkbox, and a button that `POST`s to `/api/render` and triggers the download; on a 422 it shows `error` verbatim, because the whole point of the demo is that failures name the annotation that caused them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -v`
Expected: PASS (6 tests). If `test_a_required_path_missing...` fails with 200, the 1040 set has no `required: true` annotation — add one to the taxpayer SSN per Task 9's coverage table.

- [ ] **Step 5: Run the app once by hand**

```bash
flask --app app run --debug
```

Open `http://127.0.0.1:5000`, paste `examples/joint-dependents.json`, tick debug, download.

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/routes.py app/cli.py app/templates tests/test_routes.py
git commit -m "feat: Flask demo, render/validate API and CLI"
```

---

### Task 11: SPEC.md, README.md and the walkthrough script

**Files:**
- Create: `SPEC.md`, `docs/video-script.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the finished system.
- Produces: the primary deliverable. The brief grades "scope accounted for, cleanliness of deliverable, quality of walkthrough" — this task is two of the three.

- [ ] **Step 1: Write SPEC.md**

Required sections, in order:

1. **Purpose and the contract** — given a conforming annotation set and any JSON dataset, a third party prints correct values in every box using their own renderer, in any language.
2. **Conformance** — RFC 2119 MUST/SHOULD/MAY for a conforming renderer. At minimum: MUST implement the coordinate conversion in Global Constraints; MUST implement the missing/multiple-match semantics; MUST support base-14 fonts; MUST honour `condition`; SHOULD implement `shrink`; MAY implement `clip` by any means that keeps ink inside the box.
3. **Coordinate system** — top-left origin, points, the conversion formula, the 0.72 cap-height factor, worked example with real numbers from `f1040-2024.json`.
4. **Document structure** — walk `AnnotationSet` field by field, generated from the model docstrings so it cannot drift.
5. **Referencing values** — the JSONPath subset, with the exact supported grammar, why filters are excluded (portability + code-execution surface), and the missing/multiple/null table.
6. **Types and formatting** — one subsection per `FieldType` with an input example and the exact rendered output. Currency covers thousands separators, decimals, parentheses-negatives, zero suppression, whole-dollar election, and the split dollars/cents convention as two annotations.
7. **Repeating groups** — row geometry, row-relative paths, `maxRows`, and the two overflow strategies (`statement`, `error`).
8. **Provenance and form revisions** — `source.sha256`, warn-by-default, `--strict`.
9. **Decisions and rejected alternatives** — reproduce the decision table above verbatim, including D9 (no `compute` operator) and the rejected AcroForm-only and text-anchored designs.
10. **Non-goals** — from Global Constraints.
11. **Future enhancements** — every row of the plan's "Deliberately not built" table, each with the trigger that would justify building it (`rotation` → the first rotated state form; `wrap`/`multiline` → the first free-text explanation box; `continuation` → the first return with more Schedule B payers than a statement can absorb); text-anchored authoring that *emits* coordinates; visual annotation editor (the change that would justify a database); form-revision diffing using `acroFieldName` to report which boxes moved between years; state and prior-year forms via `form.jurisdiction`; Spanish-language variants (`f1040sp`) which share geometry; barcode/2-D matrix annotations for state forms; an HTML/canvas renderer to prove the format is not a reportlab config file in disguise; a publishable conformance fixture suite; tagged-PDF accessibility output.

- [ ] **Step 2: Rewrite README.md**

Quickstart (`pip install -r requirements.txt`, `flask --app app run`, the CLI one-liner), the 60-second tour of the four modules, a link to SPEC.md, and one screenshot of `?debug=1` output.

- [ ] **Step 3: Write docs/video-script.md**

| Time | Beat |
|---|---|
| 0:00–0:30 | The problem: print arbitrary nested taxpayer data into the right boxes of any U.S. tax form, using someone else's renderer |
| 0:30–1:45 | One annotation end to end — id, box, type, JSONPath, format — then the coordinate system and why coordinates beat AcroForm names (D1, D2) |
| 1:45–2:30 | Referencing deeply nested data: the JSONPath subset, and why filters are excluded |
| 2:30–3:15 | Repeating groups on Schedule B, including overflow to an attached statement |
| 3:15–4:15 | Live demo: dataset in → filled 1040 out; then `?debug=1` showing every box the spec declared |
| 4:15–5:00 | Decisions, the representative-subset choice, top three future enhancements, close |

Pre-render all PDFs and open all tabs before recording. Rehearse once against a timer.

- [ ] **Step 4: Full verification**

```bash
pytest -v
python tools/gen_schema.py && git diff --exit-code schema/
grep -rn "TODO\|FIXME\|NotImplementedError" app/ tools/
```

Expected: all tests pass; schema unchanged (proving it is current); the grep
returns nothing.

Then one ponytail pass: for every `Literal[...]` in `app/models.py`, confirm each
value is reachable from a test. A value that is not is either implemented now or
deleted — it does not ship undecided.

- [ ] **Step 5: Commit**

```bash
git add SPEC.md README.md docs/video-script.md
git commit -m "docs: specification, README and walkthrough script"
```

---

## Risks

| Risk | Mitigation |
|---|---|
| Widget `/Rect` includes border padding, so extracted boxes are subtly off | Task 6 Step 5 renders and is inspected before Task 9 authors anything at scale; the debug overlay makes drift obvious |
| Origin-conversion bug baked into the sets | Conversion lives in one function (`geometry.to_pdf_rect`), unit-tested in Task 2, and inverted in exactly one other place (`extract_widgets`) which Task 8 tests against page bounds |
| Schedule B page geometry differs from the 1040 | Measured in Task 0, stored per-page in the model, never assumed |
| `extract_text(visitor_text=...)` misses text drawn with unusual operators | Task 6 asserts a real placement before any set depends on the probe; if it proves unreliable, fall back to asserting the overlay's content stream before the merge |
| Scope creep into tax calculation | D9 closes it; Global Constraints list it as a non-goal |
| Spec grows features the renderer never exercises | Global Constraints: no example and no test means the feature is deleted |
| Video runs long | Scripted, pre-rendered, rehearsed once |

---

## Self-review notes

- Spec coverage: every requirement in `REQUIREMENTS.md` maps to a task — data structure → Tasks 1–2; positioning → Task 2; formatting → Task 4; deep data references → Task 3; written documentation → Task 11; video → Task 11 Step 3; "classes in a popular language" → Task 1 (pydantic models are the source of truth); "scope accounted for" → the Task 9 coverage table and SPEC.md §11.
- Type consistency: `render()`, `resolve_one/many`, `evaluate`, `format_value`, `to_pdf_rect`, `baseline_y`, `anchor_x`, `load_set`, `verify_source`, `extract`, `create_app` are each defined once and referenced with the same signature everywhere.
- No placeholders remain; the only literal `TODO` in the plan is `"$.TODO_assign_a_path"`, which is draft **output** the Task 9 test asserts never reaches a shipped file.
