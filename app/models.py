from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, model_validator

BASE14 = {"Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
          "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
          "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
          "Symbol", "ZapfDingbats"}

FieldType = Literal["text", "currency", "integer", "decimal",
                    "date", "ssn", "ein", "phone", "zip", "checkbox", "comb"]
# ponytail: no "multiline" — nothing in the v1 sets wraps, and a wrap engine
# with no caller is a spec promise no third party could verify. See SPEC.md §11.


class Box(BaseModel):
    """Top-left origin, y grows down, units are PDF points."""
    x: float
    y: float
    width: float
    height: float


class Style(BaseModel):
    font: str = "Helvetica"
    fontFallback: str | None = None
    size: float = 9.0
    color: str = "#000000"
    align: Literal["left", "center", "right"] = "left"
    valign: Literal["top", "middle", "bottom"] = "middle"
    padding: float = 1.5
    # ponytail: no letterSpacing (comb already owns character pitch) and no
    # rotation (no box in the v1 sets is rotated). Both in SPEC.md §11.

    @model_validator(mode="after")
    def _base14_or_fallback(self):
        if self.font not in BASE14 and self.fontFallback is None:
            raise ValueError(
                f"font {self.font!r} is not base-14; a fontFallback is required")
        if self.fontFallback is not None and self.fontFallback not in BASE14:
            raise ValueError(f"fontFallback {self.fontFallback!r} is not base-14")
        return self


class Condition(BaseModel):
    """Deliberately an object, not a JSONPath predicate: the spec's JSONPath
    subset excludes filter expressions, so it cannot express a comparison."""
    path: str
    op: Literal["exists", "absent", "truthy", "equals", "notEquals"] = "truthy"
    value: object | None = None

    @model_validator(mode="after")
    def _value_required_for_comparisons(self):
        if self.op in ("equals", "notEquals") and self.value is None:
            raise ValueError(f"op {self.op!r} requires a value")
        return self


class Format(BaseModel):
    decimals: int = 2
    thousandsSeparator: bool = True
    negative: Literal["parentheses", "minus"] = "parentheses"
    zeroSuppress: bool = True
    wholeDollars: bool = False
    datePattern: str = "%m/%d/%Y"
    cells: int | None = None          # comb: number of character cells
    checkedGlyph: str = "X"
    trueValues: list[object] = Field(default_factory=lambda: [True, "true", "Y", "yes", 1])


class FieldAnnotation(BaseModel):
    kind: Literal["field"] = "field"
    id: str
    label: str
    page: int
    box: Box
    type: FieldType
    value: str                        # JSONPath, relative to the row inside a group
    acroFieldName: str | None = None  # hint only; coordinates win on conflict
    required: bool = False
    format: Format = Field(default_factory=Format)
    style: Style = Field(default_factory=Style)
    # ponytail: shrink | clip | error only. "wrap" and "truncate" had no
    # implementation and no test, so they were cut rather than shipped as
    # enum values a conforming renderer could not actually rely on.
    overflow: Literal["shrink", "clip", "error"] = "shrink"
    minSize: float = 5.0
    condition: Condition | None = None

    @model_validator(mode="after")
    def _comb_needs_cells(self):
        if self.type == "comb" and not self.format.cells:
            raise ValueError(f"{self.id}: comb annotations require format.cells")
        return self


class GroupAnnotation(BaseModel):
    kind: Literal["group"]
    id: str
    label: str
    page: int
    source: str                       # JSONPath to an array
    rowHeight: float
    maxRows: int
    firstRowBox: Box
    columns: list[FieldAnnotation]
    # ponytail: "continuation" (spill onto a second page) needs page cloning
    # the v1 renderer does not do. Cut, not reserved. SPEC.md §11.
    overflowStrategy: Literal["statement", "error"] = "statement"
    # The id of a FieldAnnotation elsewhere in this set. That field is removed
    # from the normal field pass and printed ONLY when this group overflows.
    overflowTarget: str | None = None
    condition: Condition | None = None


Annotation = Annotated[Union[FieldAnnotation, GroupAnnotation],
                       Field(discriminator="kind")]


class FormMeta(BaseModel):
    id: str
    title: str
    taxYear: int
    revision: str
    jurisdiction: str = "US-IRS"


class SourceMeta(BaseModel):
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pageCount: int


class PageMeta(BaseModel):
    number: int
    width: float
    height: float


class AnnotationSet(BaseModel):
    specVersion: Literal["1.0"]
    form: FormMeta
    source: SourceMeta
    pages: list[PageMeta]
    defaults: Style = Field(default_factory=Style)
    annotations: list[Annotation]

    @model_validator(mode="after")
    def _referential_integrity(self):
        pages = {p.number for p in self.pages}
        seen: set[str] = set()
        for a in self.annotations:
            if a.page not in pages:
                raise ValueError(f"{a.id}: page {a.page} is not declared in pages[]")
            if a.id in seen:
                raise ValueError(f"duplicate annotation id {a.id!r}")
            seen.add(a.id)
            if isinstance(a, GroupAnnotation):
                for c in a.columns:
                    if c.id in seen:
                        raise ValueError(f"duplicate annotation id {c.id!r}")
                    seen.add(c.id)
                if a.overflowStrategy == "statement" and not a.overflowTarget:
                    raise ValueError(
                        f"{a.id}: overflowStrategy 'statement' requires overflowTarget")
        return self
