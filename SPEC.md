# Tax Form Annotation Specification v1.0

## 1. Purpose and the Contract
This specification defines a JSON-based format for annotating United States tax forms.
Given a conforming annotation set and any JSON dataset, a third party can print correct values in every box using their own renderer, in any language.

## 2. Conformance
The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

For a conforming renderer:
- MUST implement the coordinate conversion in Global Constraints.
- MUST implement the missing/multiple-match semantics.
- MUST support base-14 fonts.
- MUST honour `condition`.
- SHOULD implement `shrink`.
- MAY implement `clip` by any means that keeps ink inside the box.
- `overflowTarget` MUST name a top-level `FieldAnnotation` (not a group column).
- `page` MUST be declared and match a page in `pages[]`.
- Annotation `id`s MUST be unique across the document.
- `comb` REQUIRES `format.cells`.
- Non-base-14 font in `style.font` REQUIRES `style.fontFallback` naming a base-14 substitute.

## 3. Coordinate System
- **Origin**: Top-left origin, `y` grows down, `x` grows right.
- **Unit**: PDF points (1/72 of an inch).
- **Conversion to PDF User Space**: `y_pdf_bottom = page_height - y - height`.
- **Cap-Height Factor**: Pinned at `0.72 × fontSize` for vertical alignment.

*Worked Example:*
A box on `f1040-2024.json` with `x: 40`, `y: 96`, `width: 200`, `height: 14` on a page with height `792`.
PDF `y_bottom` = `792 - 96 - 14 = 682`.

## 4. Document Structure
An `AnnotationSet` consists of:
- `specVersion`: `"1.0"`
- `form`: Form metadata (`id`, `title`, `taxYear`, `revision`, `jurisdiction`).
- `source`: PDF source metadata (`url`, `sha256`, `pageCount`).
- `pages`: List of pages with their measured `width` and `height`.
- `defaults`: Default styling.
- `annotations`: A flat list of annotations, discriminated by `kind: "field" | "group"`.

## 5. Referencing Values
Data is referenced using a strict subset of JSONPath.
**Grammar supported**: child access (`$.foo.bar`), array index (`[0]`), wildcard (`[*]`), and deep scan (`..`).
**Excluded**: Filter expressions (e.g., `[?(@.wages > 1000)]`) are explicitly rejected to guarantee portability and prevent code-execution surfaces.

*Missing/Multiple Semantics:*
- Explicit JSON `null` is treated identically to absent.
- `required: true` on a path resolving to `null`/absent raises `MissingValueError`.
- A path resolving to zero matches prints nothing (unless `required: true`).
- A path resolving to more than one match on a `field` annotation raises an error (multiplicity is only valid in groups).
- `notEquals` against a missing path returns `True` (vacuous truth); `exists: false`, `absent: true`, `truthy: false`, `equals: false`.
- Group array paths resolve matches in document order.

## 6. Types and Formatting
- `text`, `integer`, `decimal`, `ssn`, `ein`, `phone`, `zip`: standard text formatting.
- `date`: Uses `datePattern`. (e.g., `fiscal_year_begin_date` as `f1_01` on p1).
- `checkbox`: Uses `checkedGlyph` (e.g., `"X"`) if value matches `trueValues`.
- `comb`: Splits string into `format.cells`.
- `currency`: Supports `thousandsSeparator`, `decimals`, `negative` convention, `zeroSuppress`, and `wholeDollars`.
  - *Zero suppression* is "suppress if the ROUNDED value is zero". (e.g., 0.4 prints "0.40" at `decimals=2`, but blank under `wholeDollars: true`).
  - *Split dollars/cents* convention is mapped as two separate annotations. (e.g., line 1a wages split at 52pt / 20pt on `f1_47`).

## 7. Repeating Groups
- **Row geometry**: Driven by `firstRowBox` and `rowHeight`. Column `box.y` values are cosmetic; the renderer sets `y = firstRowBox.y + n * rowHeight`.
- **Paths**: Column paths resolve relative to the current row item.
- **Limits**: Governed by `maxRows`.
- **Overflow strategies**: `"statement"` (prints "see attached" in `overflowTarget`) or `"error"`.

## 8. Provenance and Form Revisions
- `source.sha256` ensures the annotation set matches the underlying PDF.
- A hash mismatch emits a warning by default to accommodate IRS silent reissues.
- `--strict` mode upgrades this warning to a hard failure.

## 9. Decisions and Rejected Alternatives
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

## 10. Non-goals
- No tax calculation.
- No e-file/MeF.
- No OCR.
- No PDF authoring from scratch.
- No authoring UI.
- No state forms in v1.

## 11. Future Enhancements
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
