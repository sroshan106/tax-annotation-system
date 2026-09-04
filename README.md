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
```

## Architecture Tour

The reference pipeline operates in 4 decoupled modules:
- **`loader.py`**: Reads and validates the annotation set, checking source PDF sha256.
- **`resolver.py`**: Evaluates JSONPath subsets and conditions against the dataset.
- **`formatter.py`**: Converts typed values into formatted display strings (e.g., currency, combs).
- **`renderer.py`**: Draws the glyphs on a `reportlab` overlay and merges it onto the unmodified IRS PDF using `pypdf`.

## Specification

Read the full format specification here: [SPEC.md](SPEC.md).

## Web Interface & Debug Mode

The Flask app exposes an endpoint that renders PDFs directly from the browser.
Append `?debug=1` to the render URL to draw every declared bounding box on the PDF.
*(Screenshot: Imagine a 1040 with red and blue debug boxes highlighting every text and group field)*
