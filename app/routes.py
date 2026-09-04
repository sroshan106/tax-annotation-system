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
