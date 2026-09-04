# Tax Form Annotation Spec

A machine-checkable data structure and reference pipeline for printing values from an arbitrary JSON dataset into the correct boxes of a U.S. tax form.

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the CLI to generate a filled PDF
python app/cli.py render annotations/f1040-2024.json examples/simple-w2.json output.pdf

# 3. Or run the Flask demo
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

The reference pipeline operates in 4 decoupled modules:
- **`loader.py`**: Reads and validates the annotation set, checking source PDF sha256.
- **`resolver.py`**: Evaluates JSONPath subsets and conditions against the dataset.
- **`formatter.py`**: Converts typed values into formatted display strings (e.g., currency, combs).
- **`renderer.py`**: Draws the glyphs on a `reportlab` overlay and merges it onto the unmodified IRS PDF using `pypdf`.

## Specification

Read the full format specification here: [SPEC.md](./SPEC.md).

## Web Interface & Debug Mode

The Flask app exposes an endpoint that renders PDFs directly from the browser.
Append `?debug=1` to the render URL to draw every declared bounding box on the PDF.
*(Screenshot: Imagine a 1040 with red and blue debug boxes highlighting every text and group field)*

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
