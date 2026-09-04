"""Resolution of the spec's JSONPath subset.

Imports the BASE jsonpath_ng parser, never jsonpath_ng.ext. The base grammar
has no filter or script expressions, so the portable subset the spec promises
is enforced by construction rather than by a blocklist.
"""
from functools import lru_cache
from jsonpath_ng import parse as _parse
from app.models import Condition


class MissingValueError(KeyError): ...
class MultipleMatchesError(ValueError): ...
class UnsupportedPathError(ValueError): ...


@lru_cache(maxsize=512)
def _compile(path: str):
    try:
        return _parse(path)
    except Exception as exc:  # parser/lexer raise broadly
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
