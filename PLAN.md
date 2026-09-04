# Implementation Plan — Tax Form Annotation Spec (Instead technical test)

Status: plan only. No code written yet.
Date: 2026-09-04
Stack: Python 3.12 · Flask 3.1 · pypdf · reportlab

---

## 1. What is being delivered

The requirement asks for a **data structure**, not an application. The application exists to
prove the data structure is sufficient.

Four deliverables:

| # | Deliverable | Form |
|---|-------------|------|
| D1 | The annotation specification | `SPEC.md` — prose + normative rules |
| D2 | The machine-readable schema | `schema/annotation-set.schema.json` (JSON Schema 2020-12) |
| D3 | Real annotation sets | `annotations/f1040-2024.json`, `annotations/f1040sb-2024.json` |
| D4 | Reference renderer | Flask app that consumes D2 + D3 + a taxpayer dataset and emits a filled PDF |

Plus a ≤5 min video walkthrough (script outlined in §9).

**The contract being asserted:** given an annotation set conforming to D2 and an arbitrary
JSON dataset, a third party can print correct values inside every box of the form using
their own rendering code, in any language, with no access to our implementation.

---

## 2. Decisions made (and why)

Decisions confirmed with the reviewer before planning. Recorded here because the requirement
explicitly asks that decisions be described.

### 2.1 Positioning: coordinates primary, AcroForm name optional

Annotation carries a required geometric anchor `{page, x, y, width, height}` and an
**optional** `acroFieldName` hint. On conflict, **coordinates win**; the field name is a
cross-check and an interop convenience, never a second rendering path.

Rejected alternatives:
- *AcroForm names only* — fails on non-fillable and scanned state forms, delegates all
  formatting to the PDF viewer, and IRS field names (`f1_09[0]`) are opaque and churn yearly.
  The requirement's wording ("print values **on top of** the forms within each box") is an
  overlay model; AcroForm cannot express *how* to print.
- *Text-relative anchors* (DocuSign-style "2pt right of the string `Line 12a`") — most robust
  against layout drift, but forces every conforming renderer to depend on PDF text extraction,
  and is non-deterministic on scanned forms and duplicated labels. Deferred to §8 as an
  authoring-time feature that *generates* coordinates, not a runtime anchor type.

### 2.2 Coordinate system: top-left origin, y grows down, unit = PDF point (1/72")

Declared once, normatively, in the spec. PDF's native origin is bottom-left; the spec chooses
top-left because it matches how humans read a page, how HTML/canvas consumers work, and how
annotations get authored and debugged. Conversion is one subtraction the renderer does:
`y_pdf = page_height - y_spec - height`. The spec states this formula explicitly so no
implementer has to guess.

### 2.3 Data references: documented JSONPath subset

`"value": "$.income.w2[0].wages"`. JSONPath is a de facto standard with libraries in every
language, which matters because the consumer's renderer is "their proprietary code."

The spec pins a **safe subset** — child access, array index, wildcard, and a small set of
recursive-descent cases. Filter expressions and script expressions are **excluded**: they are
the inconsistently-implemented part of JSONPath and a code-execution surface. Excluding them
is what makes the subset portable.

Rejected: custom dotted paths (non-standard, weak on arrays), JSON Pointer (an actual RFC and
dead simple, but no wildcards — every cross-row sum would need a computed field).

### 2.4 Storage: JSON files in the repo

One file per form + tax year, versioned in git. No database, no migrations, no CRUD layer.
An annotation set for a given form-year is immutable published data, which is exactly what a
file in version control is. A DB would be justified only by an authoring UI, which is out of
scope (§8).

### 2.5 Renderer: reportlab overlay merged onto the original IRS PDF with pypdf

reportlab draws a transparent text layer; pypdf merges it over the unmodified government PDF.
Both permissively licensed. Rejected PyMuPDF despite better ergonomics — AGPL is a
non-starter for a commercial tax platform. Rejected pypdf-only — its text drawing lacks the
alignment, clipping, and character-pitch control the spec's formatting rules require.

### 2.6 Scope: Form 1040 pages 1–2 + Schedule B

Chosen for edge-case coverage per unit of authoring effort:

- **1040 p1** — text, name/address, comb-box SSN, mutually-exclusive filing-status checkboxes,
  dependents table (bounded repeating rows), currency lines.
- **1040 p2** — currency, signature/date block, negative-value and zero-suppression cases,
  multi-page continuation of the same logical document.
- **Schedule B** — payer lists in Part I / Part II are genuine unbounded repeating rows with
  overflow behaviour. This is the case that proves repeating groups and array JSONPath work.

---

## 3. Verified facts about the source material

Checked before planning, not assumed:

- `https://www.irs.gov/pub/irs-pdf/f1040.pdf` is reachable, 2 pages, ~215 KB, PDF 1.7.
- MediaBox is `[0, 0, 612, 792]` — US Letter, so 1pt = 1/72 inch and no page-scaling factor.
- The PDF carries **229 AcroForm fields** (`topmostSubform[0].Page1[0].f1_01[0]` etc.).
- Local env: Python 3.12.3, Flask 3.1.3, pypdf 6.16.1 present. reportlab must be installed.

**Consequence for the plan:** each AcroForm field has a widget annotation with a `/Rect`.
Those rects are the IRS's own box geometry. The annotation sets are therefore **bootstrapped by
extraction, not measured by hand** — a script walks the widgets and emits draft annotations with
coordinates, `acroFieldName`, and an inferred type already filled in. Human effort collapses to
naming each annotation, assigning its JSONPath, and fixing the handful of boxes the heuristics
get wrong. This is the single largest risk reduction in the plan.

---

## 4. Specification design

Sketch sufficient to review the shape. Exact field names finalised while writing `SPEC.md`.

### 4.1 Document structure

```
AnnotationSet
├── specVersion            "1.0"           semver of THIS spec
├── form                   { id, title, taxYear, revision, jurisdiction }
├── source                 { url, sha256, pageCount, pageSize }   provenance + integrity
├── defaults               inherited style: font, size, color, align, padding
├── pages[]                { number, width, height }
└── annotations[]          the payload
```

`source.sha256` pins the exact government PDF the coordinates were authored against. A renderer
can refuse, or warn, when handed a different revision. This is the answer to "what happens when
the IRS reissues the form."

### 4.2 The annotation object

```
Annotation
├── id                     stable, human-meaningful: "line_1a_wages"
├── label                  human description, for tooling and debugging
├── page                   1-based
├── box                    { x, y, width, height }  top-left origin, points
├── acroFieldName?         optional hint; coordinates win on conflict
├── type                   text | currency | integer | decimal | date | ssn | ein
│                          | phone | zip | checkbox | radioGroup | comb | multiline
├── value                  JSONPath into the taxpayer dataset
├── format?                type-specific rules (§4.3)
├── style?                 font, size, weight, color, align, valign, letterSpacing
├── overflow?              shrink | clip | truncate | wrap | error
└── condition?             optional JSONPath predicate gating whether it prints at all
```

### 4.3 Formatting rules the spec must pin down

Formatting is where most "just print it in the box" specs quietly fail. Enumerated so the
renderer has no discretion:

- **currency** — thousands separator, decimal places, whether the cents column is a separate
  box (the 1040 splits dollars and cents on many lines), negative representation
  (parentheses vs minus — IRS convention is parentheses), zero suppression, and the
  round-to-whole-dollars election.
- **comb** — N character cells at fixed pitch across the box, used for SSN, EIN, ZIP. Spec
  gives cell count and pitch; renderer distributes glyphs by cell centre, not by string width.
- **checkbox** — glyph (`X`, `✓`), and how truthiness is decided from the referenced value.
- **radioGroup** — a set of boxes where exactly one prints; the spec must state what happens
  when the data matches zero or more than one.
- **date** — output pattern, and the input format expected in the dataset (ISO 8601).
- **overflow** — the default is `shrink` to a stated minimum font size, then `clip`. `error` is
  available for values that must never be silently truncated.
- **text alignment** — currency right-aligns to the box's inner edge; the spec defines padding
  so two renderers put the same digit in the same place.

### 4.4 Repeating groups (Schedule B)

```
RepeatingGroup
├── id                     "sch_b_part1_payers"
├── source                 JSONPath to the array: "$.income.interest[*]"
├── rowHeight              points
├── maxRows                rows printable on the form
├── firstRowBox            anchor for row 0
├── columns[]              annotations with box.x/width relative to the row
├── overflowStrategy       continuation | statement | error
└── overflowTarget?        annotation id for "see attached statement"
```

Row *n* is drawn at `firstRowBox.y + n * rowHeight`. Column `value` paths are **relative to the
row item** (`$.payer`, `$.amount`), so a nested array is addressed once at the group level
rather than repeated per cell. When rows exceed `maxRows`, `overflowStrategy` decides between a
continuation page, a total-plus-attached-statement, and a hard error.

### 4.5 Computed values

Some boxes are sums, not data (`Line 9 = 1z + 2b + 3b + ...`). Two candidate approaches, to be
settled in the first implementation phase:

- **(preferred)** Keep the spec pure — computed lines are just JSONPaths into a dataset the
  caller already computed. The annotation spec describes *placement and presentation*, not tax
  logic, and tax logic is the platform's crown jewel, not an annotation concern.
- **(alternative)** A tiny declarative `compute: { op: "sum", of: [...] }`. Convenient, but
  opens the door to expressing tax computation in an annotation file, which is the wrong layer.

Plan proceeds with the pure approach; the alternative is documented in `SPEC.md` as a
deliberately rejected option so reviewers see it was considered.

### 4.6 Explicit non-goals

Stated in the spec so scope is legible: no tax calculation, no e-file/MeF XML schema, no PDF
generation from scratch, no OCR, no form-layout authoring UI, no state forms in v1.

---

## 5. Repository layout

```
instead/
├── README.md                          what this is, how to run, 60-second tour
├── SPEC.md                            D1 — the specification
├── PLAN.md                            this file
├── REQUIREMENTS.md                    the original brief
├── schema/
│   └── annotation-set.schema.json     D2 — JSON Schema 2020-12
├── annotations/
│   ├── f1040-2024.json                D3
│   └── f1040sb-2024.json
├── forms/                             cached IRS PDFs (checked in, sha256 pinned in the set)
├── examples/
│   ├── simple-w2.json                 single filer, one W-2
│   ├── joint-dependents.json          MFJ, dependents table, negative values
│   └── schedule-b-overflow.json       more payers than rows — exercises overflow
├── app/
│   ├── __init__.py                    Flask app factory
│   ├── routes.py                      HTTP layer only
│   ├── loader.py                      load + schema-validate an annotation set
│   ├── resolver.py                    JSONPath subset resolution
│   ├── formatter.py                   value -> display string, per type
│   ├── renderer.py                    display string -> drawn glyphs on the overlay
│   └── templates/index.html           demo page
├── tools/
│   ├── extract_widgets.py             AcroForm rects -> draft annotation set (§3)
│   └── validate.py                    CLI: validate a set against schema + source PDF
└── tests/
```

The four-module split (`loader` / `resolver` / `formatter` / `renderer`) is the spec's own
pipeline made executable: **load → resolve → format → draw**. Each stage is independently
testable, and the boundaries are the same boundaries a third-party implementer will hit. A
reviewer reading `renderer.py` should find it contains no tax knowledge and no JSONPath.

---

## 6. Build phases

Each phase ends in something runnable.

**Phase 0 — Groundwork**
Vendor `f1040.pdf` and `f1040sb.pdf` into `forms/`, record sha256. `requirements.txt`
(flask, pypdf, reportlab, jsonschema, jsonpath-ng). Confirm the exact page count and MediaBox
of Schedule B the same way 1040 was confirmed — do not assume it is Letter.

**Phase 1 — Schema and spec skeleton**
Write `annotation-set.schema.json` first: the schema is the contract, prose follows it. Draft
`SPEC.md` §§ structure, coordinate system, types. Hand-author a ~6-annotation set for the 1040
name/address/SSN block only.

**Phase 2 — Renderer spine**
`loader → resolver → formatter → renderer`, enough to print those 6 annotations onto page 1.
First visual proof the coordinate convention and the top-left→PDF conversion are right. Get
this on screen before writing anything else — a wrong origin discovered here costs minutes,
discovered in Phase 4 it costs the annotation sets.

**Phase 3 — Extraction tooling**
`tools/extract_widgets.py`: walk the 229 widgets, emit a draft set with coordinates,
`acroFieldName`, and a type inferred from the field name convention (`f` = text, `c` = checkbox)
and box geometry. Then the human pass: names, JSONPaths, formats, and correcting the guesses.
This is the bulk of the elapsed time and it is mechanical.

**Phase 4 — Full type and format coverage**
currency (incl. split dollar/cents columns and parenthesised negatives), comb, checkbox,
radioGroup, date, overflow modes, `condition`. Each type ships with the example dataset that
exercises it.

**Phase 5 — Schedule B and repeating groups**
Repeating-group resolution, row iteration, and all three overflow strategies. The
`schedule-b-overflow.json` example must produce a correct, legible result — not a crash and not
silently dropped rows.

**Phase 6 — Flask app and debug overlay**
`GET /` demo page: choose form, paste or upload dataset, download filled PDF.
`POST /api/render` → `application/pdf`. `POST /api/validate` → schema + coordinate sanity report.
`?debug=1` draws box outlines and annotation ids over the form. The debug overlay is not a
nicety — it is how the spec is *shown* rather than described, in the video and in review.

**Phase 7 — Tests**
- schema: valid sets pass, each malformed case fails with a useful message
- resolver: nested objects, arrays, wildcards, missing paths, null vs absent
- formatter: currency rounding and negatives, comb distribution, date patterns, boundaries
- renderer: golden-PDF byte comparison on a fixed dataset, plus every box's drawn extent
  asserted inside its declared box (catches overflow regressions without eyeballing)
- end-to-end: each example dataset renders without error

**Phase 8 — Documentation pass**
Finish `SPEC.md` (conformance requirements — what a renderer MUST/SHOULD/MAY do — plus the
rejected-alternatives and future-enhancements sections). `README.md` quickstart. Record video.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Widget-derived coordinates are subtly off (rect includes border/padding) | Phase 2 visual check before mass extraction; debug overlay makes drift obvious at a glance |
| Origin-conversion bug baked into hand-authored sets | Convert in exactly one function; unit-test it against a known widget rect |
| Schedule B is not Letter-sized or has a different page count | Verified in Phase 0, not assumed |
| Scope creep into tax calculation | §4.6 non-goals stated up front; computed lines stay the caller's problem (§4.5) |
| Spec grows features the reference renderer never exercises | Every spec feature must appear in at least one example dataset and one test |
| Video runs over 5 minutes | Scripted (§9), rehearsed once, demo state prepared in advance |

---

## 8. Future enhancements (called out in the deliverable, per the brief)

- **Text-anchored authoring** — locate a label string, derive coordinates from it, emit a
  normal coordinate annotation. Absorbs minor IRS layout drift at authoring time without
  putting text extraction into the runtime contract.
- **Visual annotation editor** — click boxes on a rendered form to author annotations. This is
  the change that would justify the database rejected in §2.4.
- **Form-revision diffing** — given last year's set and this year's PDF, report which
  `acroFieldName`s moved, vanished, or appeared. Turns the annual re-annotation from a re-do
  into a review. The `acroFieldName` hint (§2.1) exists partly to make this possible.
- **State and prior-year forms** — same schema, `form.jurisdiction` already carries it.
- **Localisation** — Spanish-language IRS variants (`f1040sp`) share geometry, differ in labels.
- **Barcode / 2-D matrix annotations** — several state forms require a scannable block.
- **HTML/canvas renderer** — the same annotation set driving an in-browser preview, proving the
  spec is genuinely renderer-agnostic and not a reportlab config file in disguise.
- **Conformance test suite** — publishable fixture set any third-party implementation can run
  to claim conformance.
- **Accessibility** — emit tagged PDF / value-to-box mapping so filled forms are screen-readable.

---

## 9. Video walkthrough script (≤5:00)

| Time | Beat |
|------|------|
| 0:00–0:30 | Problem framing: print arbitrary nested taxpayer data into the right boxes on any US tax form, with someone else's renderer |
| 0:30–1:45 | The spec: walk one annotation end to end — id, box, type, JSONPath, format. Then coordinate system and the three anchor decisions (§2.1, §2.2) |
| 1:45–2:30 | Deep data reference: the JSONPath subset, and why filters are excluded |
| 2:30–3:15 | Repeating groups on Schedule B, including overflow |
| 3:15–4:15 | Live demo: dataset in → filled 1040 out; then `?debug=1` to show the boxes the spec declared |
| 4:15–5:00 | Decisions and trade-offs, top three future enhancements, close |

---

## 10. Open questions

None blocking. Two to settle during Phase 1, both recorded above with a stated default:

1. Computed/summed lines — proceeding with the pure approach (§4.5).
2. Whether split dollar/cents columns are two annotations or one annotation with a
   two-box format. Decide when annotating the first 1040 currency line in Phase 4.
