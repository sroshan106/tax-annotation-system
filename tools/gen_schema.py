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
