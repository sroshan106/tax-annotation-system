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
An `AnnotationSet` defines the canonical schema, composed of the following nested structures (matching `app/models.py`):

### `AnnotationSet` (Root)
- `specVersion` (`Literal["1.0"]`): Fixed spec version.
- `form` (`FormMeta`): Metadata about the form.
- `source` (`SourceMeta`): PDF source metadata.
- `pages` (`list[PageMeta]`): Array of page geometries.
- `defaults` (`Style`, optional): Default styling applied across annotations.
- `annotations` (`list[Annotation]`): A flat list of `FieldAnnotation` and `GroupAnnotation` items.

### `FormMeta`
- `id` (`str`): Form identifier (e.g. `"f1040"`).
- `title` (`str`): Human-readable form title.
- `taxYear` (`int`): Year the form corresponds to.
- `revision` (`str`): Revision date/string.
- `jurisdiction` (`str`, default: `"US-IRS"`): Governing tax body.

### `SourceMeta`
- `url` (`str`): Public URL to the original PDF.
- `sha256` (`str`): SHA-256 hash of the PDF file (pattern: `^[0-9a-f]{64}$`).
- `pageCount` (`int`): Expected number of pages in the PDF.

### `PageMeta`
- `number` (`int`): 1-indexed page number.
- `width` (`float`): Page width in points.
- `height` (`float`): Page height in points.

### `Box`
Top-left origin, `y` grows down, units are PDF points.
- `x` (`float`): X-coordinate of top-left corner.
- `y` (`float`): Y-coordinate of top-left corner.
- `width` (`float`): Width of the box.
- `height` (`float`): Height of the box.

### `Style`
- `font` (`str`, default `"Helvetica"`): Name of the font.
- `fontFallback` (`str | None`): Required base-14 fallback if `font` is not base-14.
- `size` (`float`, default `9.0`): Font size in points.
- `color` (`str`, default `"#000000"`): Hex color code.
- `align` (`Literal["left", "center", "right"]`, default `"left"`): Horizontal alignment.
- `valign` (`Literal["top", "middle", "bottom"]`, default `"middle"`): Vertical alignment.
- `padding` (`float`, default `1.5`): Inset padding in points.

### `Condition`
- `path` (`str`): JSONPath expression to evaluate.
- `op` (`Literal["exists", "absent", "truthy", "equals", "notEquals"]`, default `"truthy"`): Comparison operator.
- `value` (`object | None`): Target value; required for `"equals"` and `"notEquals"`.

### `Format`
- `decimals` (`int`, default `2`): Number of decimal places.
- `thousandsSeparator` (`bool`, default `True`): Whether to use a comma separator.
- `negative` (`Literal["parentheses", "minus"]`, default `"parentheses"`): Negative number style.
- `zeroSuppress` (`bool`, default `True`): Whether to hide zero or rounded-to-zero values.
- `wholeDollars` (`bool`, default `False`): Whether to round to the nearest whole dollar.
- `datePattern` (`str`, default `"%m/%d/%Y"`): strftime format string.
- `cells` (`int | None`): Number of character cells for `"comb"` fields.
- `checkedGlyph` (`str`, default `"X"`): Character printed if a checkbox is checked.
- `trueValues` (`list[object]`, default `[True, "true", "Y", "yes", 1]`): Values treated as checked.

### `FieldAnnotation`
- `kind` (`Literal["field"]`, default `"field"`): Discriminator.
- `id` (`str`): Unique identifier.
- `label` (`str`): Human-readable field label.
- `page` (`int`): Target page number.
- `box` (`Box`): Coordinate geometry.
- `type` (`FieldType`): One of `text`, `currency`, `integer`, `decimal`, `date`, `ssn`, `ein`, `phone`, `zip`, `checkbox`, `comb`.
- `value` (`str`): JSONPath expression referencing data.
- `acroFieldName` (`str | None`): Optional original PDF field name hint.
- `required` (`bool`, default `False`): Whether missing data raises an error.
- `format` (`Format`, default `Format()`): Field-specific formatting rules.
- `style` (`Style`, default `Style()`): Field-specific styling.
- `overflow` (`Literal["shrink", "clip", "error"]`, default `"shrink"`): Handling for text that exceeds box bounds.
- `minSize` (`float`, default `5.0`): Minimum font size when shrinking.
- `condition` (`Condition | None`): Optional conditional logic to render the field.

### `GroupAnnotation`
- `kind` (`Literal["group"]`): Discriminator.
- `id` (`str`): Unique identifier.
- `label` (`str`): Human-readable label.
- `page` (`int`): Target page number.
- `source` (`str`): JSONPath expression to an array of objects.
- `rowHeight` (`float`): Vertical distance between rows.
- `maxRows` (`int`): Maximum number of rows to print.
- `firstRowBox` (`Box`): Bounding box of the entire first row.
- `columns` (`list[FieldAnnotation]`): Fields to render per row.
- `overflowStrategy` (`Literal["statement", "error"]`, default `"statement"`): Action when row count exceeds `maxRows`.
- `overflowTarget` (`str | None`): ID of a top-level `FieldAnnotation` to print "See Attached" into (required for `"statement"` strategy).
- `condition` (`Condition | None`): Optional conditional logic to render the group.


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

The `type` field dictates how extracted values are formatted before rendering. Below is exactly how each `FieldType` is formatted.

### `text`
Simple string passthrough.
- **Input Example**: `{"value": "Ada Lovelace"}`
- **Rendered Output**: `"Ada Lovelace"`

### `integer`
Formats numeric values as whole numbers.
- **Input Example**: `{"value": 42}`
- **Rendered Output**: `"42"`

### `decimal`
Formats numeric values with `Format.decimals` (default 2) and optional thousands separators (shares implementation with `currency` via `_money()`).
- **Input Example (Default `decimals: 2`)**: `{"value": 42.5}`
- **Rendered Output**: `"42.50"`
- **Input Example (Custom `decimals: 1`)**: `{"value": 42.5}` (with `decimals: 1`)
- **Rendered Output**: `"42.5"`

### `date`
Parses ISO 8601 strings and formats them using `format.datePattern`.
- **Input Example**: `{"value": "2025-04-15"}` (with `datePattern: "%m/%d/%Y"`)
- **Rendered Output**: `"04/15/2025"`

### `checkbox`
Prints `format.checkedGlyph` if the value matches any item in `format.trueValues`.
- **Input Example**: `{"value": true}` (with `checkedGlyph: "X"`)
- **Rendered Output**: `"X"`

### `currency`
Highly configurable numeric formatting supporting decimals, thousands separators, zero suppression, and whole dollar rounding.
- **Thousands Separators**: 
  - Input: `{"value": 52000.0}`
  - Output: `"52,000.00"`
- **Decimals**:
  - Input: `{"value": 1234.567}` (with `decimals: 2`)
  - Output: `"1,234.57"`
- **Negative with Parentheses**:
  - Input: `{"value": -1234.5}` (with `negative: "parentheses"`)
  - Output: `"(1,234.50)"`
- **Negative with Minus**:
  - Input: `{"value": -12.0}` (with `negative: "minus"`)
  - Output: `"-12.00"`
- **Zero Suppression (Default behavior)**:
  - Input: `{"value": 0}`
  - Output: `""` (Empty string)
- **Zero Suppression (Rounds to zero)**:
  - Input: `{"value": 0.4}` (with `wholeDollars: true`)
  - Output: `""` (Empty string, suppressed because the ROUNDED value is zero)
- **Split Dollars/Cents Convention**:
  - Instead of a single formatted value, split dollars and cents are authored as two separate annotations. For `1234.56`, one annotation extracts and formats the dollars (`"1,234"`) and a second annotation handles the cents (`"56"`).

### `comb`
Splits a string into a list of individual character cells, discarding non-alphanumeric formatting characters (like hyphens), padding missing cells with empty strings, and raising an error if it exceeds `format.cells`.
- **Input Example**: `{"value": "123"}` (with `cells: 5`)
- **Rendered Output**: `["1", "2", "3", "", ""]`

### `ssn`
A specialized form of `comb` typically expecting 9 digits. Strips hyphens.
- **Input Example**: `{"value": "123-45-6789"}` (with `cells: 9`)
- **Rendered Output**: `["1", "2", "3", "4", "5", "6", "7", "8", "9"]`

### `ein`
Similar to `ssn`, specialized for Employer Identification Numbers.
- **Input Example**: `{"value": "12-3456789"}` (with `cells: 9`)
- **Rendered Output**: `["1", "2", "3", "4", "5", "6", "7", "8", "9"]`

### `phone`
Similar to `comb`, specialized for phone numbers.
- **Input Example**: `{"value": "555-1234"}` (with `cells: 7`)
- **Rendered Output**: `["5", "5", "5", "1", "2", "3", "4"]`

### `zip`
Similar to `comb`, specialized for Zip codes.
- **Input Example**: `{"value": "021"}` (with `cells: 5`)
- **Rendered Output**: `["0", "2", "1", "", ""]`

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
