# Tax Form Annotation Spec

A machine-checkable data structure and reference pipeline for printing values from an arbitrary JSON dataset into the correct boxes of a U.S. tax form.

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the CLI to generate a filled PDF
python app/cli.py annotations/f1040-2024.json examples/simple-w2.json -o output.pdf

# Or render with debug bounding boxes
python app/cli.py annotations/f1040-2024.json examples/simple-w2.json -o output.pdf --debug

# 3. Or run the interactive Flask demo
flask --app app run

# 4. Or run with Gunicorn in production
gunicorn wsgi:app --bind 0.0.0.0:8000
```

## Deployment (Render)

This repository includes a turnkey **Render Blueprint** (`render.yaml`) and Docker container configuration:

### Option A: Render Blueprint (Infrastructure-as-Code)
1. Push this repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com/), select **New > Blueprint**.
3. Connect your repository. Render will automatically parse `render.yaml` and configure:
   * **Runtime**: Python 3.12 with Gunicorn
   * **Build command**: `pip install -r requirements.txt`
   * **Start command**: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
   * **Health check path**: `/healthz`

### Option B: Docker Web Service
You can also deploy as a Docker service on Render or any container host using the included `Dockerfile`:
```bash
docker build -t tax-annotation-system .
docker run -p 8000:8000 tax-annotation-system
```


## Architecture Tour

The reference pipeline operates in decoupled modules:
- **`models.py`**: Canonical Pydantic v2 schemas, per-type format constraints, and load-time page bounds verification.
- **`geometry.py`**: Coordinate transformations (top-left origin to PDF user-space) and optical cap-height vertical alignment.
- **`loader.py`**: Deserializes annotation sets and verifies source PDF SHA-256 and dimensions.
- **`resolver.py`**: Evaluates sandboxed JSONPath queries and conditions against arbitrary datasets.
- **`formatter.py`**: Formats typed values (Banker's rounding, comb character cell splitting, date patterns, zero suppression).
- **`renderer.py`**: Generates transparent ReportLab vector overlays with two-pass group overflow handling and merges them onto unmodified IRS PDFs via `pypdf`.

## Specification

Read the full format specification here: [SPEC.md](./SPEC.md).

## Web Interface & REST API

The Flask app provides an interactive split-view frontend (`app/templates/index.html`) featuring form/example selectors, a live JSON editor, embedded PDF preview, and a debug bounding box toggle.

### REST Endpoints
- **`POST /api/render`**: Accepts `{ form: "f1040", data: {...}, debug: false }` and returns the generated PDF (`application/pdf`).
- **`POST /api/validate`**: Accepts `{ form: "f1040" }` and returns `{ valid: true, warnings: [], errors: [] }`.
- **`GET /api/forms/<form_id>/info`**: Returns form metadata, page count, and total declared annotations.
- **`GET /api/examples/<filename>`**: Returns pre-packaged taxpayer JSON payloads.
- **`GET /healthz`**: Liveness probe returning `{"status": "healthy"}`.
- **`GET /favicon.ico`**: Serves application favicon.

## Testing & Verification

Run the test suite using pytest:
```bash
pytest
```
Tests use a placement visitor (`tests/pdf_probe.py`) to verify text glyph positions and font metrics directly from rendered PDF streams without brittle binary hash comparisons.

## Decisions and Rejected Alternatives

| # | Decision | Why |
|---|---|---|
| D1 | Coordinates are the primary anchor; `acroFieldName` is an optional cross-check hint. Coordinates win on conflict. | AcroForm names fail on scanned/non-fillable forms, are opaque, churn yearly, and cannot express *how* to print. |
| D2 | Top-left origin. | Matches how humans author and how HTML/canvas consumers work. |
| D3 | Values referenced by a documented JSONPath subset. | De facto standard with libraries in every language. Filters excluded: inconsistently-implemented and a code-execution surface. |
| D4 | Pydantic v2 models are canonical; `schema/annotation-set.schema.json` is generated. | One artifact yields both formats and gives validation for free. |
| D5 | Annotation sets are JSON files in git, one per form-year. | Published form-year data is immutable. A database is only justified by an authoring UI, which is out of scope. |
| D6 | reportlab overlay merged by pypdf onto the untouched IRS PDF. | Both permissively licensed. pypdf-only rejected: no alignment/clipping/pitch control. |
| D7 | `condition` is an object `{ path, op, value? }`, **not** a JSONPath predicate. | A predicate would need the filter grammar D3 excludes. |
| D8 | Split dollar/cents lines are **two annotations** sharing an id prefix. | `box` is one rect. A "two-box format" would contradict the model for one form's convention. |
| D9 | Computed lines (`Line 9 = 1z + 2b + …`) are plain JSONPaths into a dataset the caller already computed. No `compute` operator. | Tax logic is the platform's crown jewel and belongs a layer up. |
| D10 | Annotation sets cover a **representative subset**, not all widgets. | Past ~40 annotations the work is mechanical and adds no new evidence about the spec. |
| D11 | `source.sha256` mismatch is a **warning**, not a hard failure, unless `--strict`. | IRS silently reissues PDFs at the same URL. |

## Non-goals

- No tax calculation.
- No e-file/MeF.
- No OCR.
- No PDF authoring from scratch.
- No authoring UI.
- No state forms in v1.

## Future Enhancements

Deliberately not built in v1, but considered for future iterations:
- **`Style.rotation`**: Triggered by the first rotated state form.
- **`overflow: "wrap"` / `"truncate"` / `FieldType: "multiline"`**: Triggered by the first free-text explanation box.
- **`overflowStrategy: "continuation"`**: Triggered by the first return with more Schedule B payers than a statement can absorb.
- **Text-anchored authoring**: That *emits* coordinates.
- **Visual annotation editor**: The change that would justify a database.
- **Form-revision diffing**: Using `acroFieldName` to report which boxes moved between years.
- **State and prior-year forms**: Via `form.jurisdiction`.
- **Spanish-language variants (`f1040sp`)**: Which share geometry.
- **Barcode/2-D matrix annotations**: For state forms.
- **HTML/canvas renderer**: To prove the format is not a reportlab config file in disguise.
- **Publishable conformance fixture suite**.
- **Tagged-PDF accessibility output**.
- **Limitations**: Group model v1 column-major checkbox grids cannot be expressed as row-major group columns.
