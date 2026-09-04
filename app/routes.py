from pathlib import Path
from flask import Blueprint, jsonify, render_template, request, send_file
import io
import json

from app.loader import load_set, verify_source
from app.renderer import render
from app.resolver import MissingValueError, MultipleMatchesError, UnsupportedPathError

bp = Blueprint("main", __name__)

FORMS = {
    "f1040":   (Path("annotations/f1040-2024.json"),   Path("forms/f1040.pdf")),
    "f1040sb": (Path("annotations/f1040sb-2024.json"), Path("forms/f1040sb.pdf")),
}
EXAMPLES_DIR = Path("examples")


@bp.get("/")
def index():
    return render_template("index.html", forms=sorted(FORMS))


@bp.post("/api/render")
def api_render():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="invalid request: payload must be a JSON object"), 400
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
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="invalid request: payload must be a JSON object"), 400
    entry = FORMS.get(body.get("form", ""))
    if entry is None:
        return jsonify(error=f"unknown form {body.get('form')!r}"), 404
    set_path, pdf_path = entry
    try:
        warnings = verify_source(load_set(set_path), pdf_path, strict=False)
    except Exception as exc:
        return jsonify(valid=False, warnings=[], errors=[str(exc)])
    return jsonify(valid=not warnings, warnings=warnings, errors=[])


@bp.get("/api/forms/<form_id>/info")
def api_form_info(form_id: str):
    entry = FORMS.get(form_id)
    if entry is None:
        return jsonify(error=f"unknown form {form_id!r}"), 404
    set_path, _ = entry
    try:
        data = json.loads(set_path.read_text())
        form_meta = data.get("form", {})
        source_meta = data.get("source", {})
        annotations = data.get("annotations", [])
        return jsonify({
            "id": form_meta.get("id", form_id),
            "title": form_meta.get("title", form_id),
            "taxYear": form_meta.get("taxYear"),
            "revision": form_meta.get("revision"),
            "jurisdiction": form_meta.get("jurisdiction"),
            "pageCount": source_meta.get("pageCount", len(data.get("pages", []))),
            "sourceUrl": source_meta.get("url"),
            "annotationCount": len(annotations),
        })
    except Exception as exc:
        return jsonify(error=str(exc)), 500


@bp.get("/api/examples/<filename>")
def api_example(filename: str):
    safe_name = Path(filename).name
    if not safe_name.endswith(".json"):
        return jsonify(error="invalid example filename"), 400
    file_path = EXAMPLES_DIR / safe_name
    if not file_path.is_file():
        return jsonify(error=f"unknown example {safe_name!r}"), 404
    try:
        data = json.loads(file_path.read_text())
        return jsonify(data)
    except Exception as exc:
        return jsonify(error=str(exc)), 500


@bp.get("/healthz")
def healthz():
    return jsonify(status="healthy"), 200

