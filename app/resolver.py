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
    except Exception as exc:
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
    present = [v for v in resolve_many(cond.path, data) if v is not None]
    first = present[0] if present else None
    if cond.op == "exists":
        return bool(present)
    if cond.op == "absent":
        return not present
    if cond.op == "truthy":
        return bool(first)
    if cond.op == "equals":
        return bool(present) and first == cond.value
    if cond.op == "notEquals":
        return not present or first != cond.value
    raise UnsupportedPathError(f"unknown condition op {cond.op!r}")
