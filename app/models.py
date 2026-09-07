from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, model_validator

BASE14 = {"Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
          "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
          "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
          "Symbol", "ZapfDingbats"}

FieldType = Literal["text", "currency", "integer", "decimal",
                    "date", "ssn", "ein", "phone", "zip", "checkbox", "comb"]

MONEY_KEYS = {"decimals", "thousandsSeparator", "negative", "zeroSuppress", "wholeDollars"}
COMB_KEYS = {"cells"}
CHECKBOX_KEYS = {"checkedGlyph", "trueValues"}

#: Which `format` keys the formatter actually reads for each field type.
#: Anything else is a no-op, so the set rejects it rather than ignoring it.
FORMAT_KEYS: dict[str, set[str]] = {
    "text": set(),
    "integer": set(),
    "currency": MONEY_KEYS,
    "decimal": MONEY_KEYS,
    "date": {"datePattern"},
    "checkbox": CHECKBOX_KEYS,
    "ssn": COMB_KEYS,
    "ein": COMB_KEYS,
    "phone": COMB_KEYS,
    "zip": COMB_KEYS,
    "comb": COMB_KEYS,
}


class Box(BaseModel):
    """Top-left origin, y grows down, units are PDF points."""
    x: float
    y: float
    width: float
    height: float

    def fits(self, page: PageMeta) -> bool:
        return (self.x >= 0 and self.y >= 0
                and self.x + self.width <= page.width
                and self.y + self.height <= page.height)


class Style(BaseModel):
    font: str = "Helvetica"
    fontFallback: str | None = None
    size: float = 9.0
    color: str = "#000000"
    align: Literal["left", "center", "right"] = "left"
    valign: Literal["top", "middle", "bottom"] = "middle"
    padding: float = 1.5

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
    cells: int | None = None
    checkedGlyph: str = "X"
    trueValues: list[object] = Field(default_factory=lambda: [True, "true", "Y", "yes", 1])


class Printable(BaseModel):
    """Everything needed to turn one resolved value into ink, minus the
    geometry, which differs between a standalone field and a group column."""
    id: str
    label: str
    type: FieldType
    value: str
    acroFieldName: str | None = None
    required: bool = False
    format: Format = Field(default_factory=Format)
    style: Style = Field(default_factory=Style)
    overflow: Literal["shrink", "clip", "error"] = "shrink"
    minSize: float = 5.0
    condition: Condition | None = None

    @model_validator(mode="after")
    def _comb_needs_cells(self):
        if self.type == "comb" and not self.format.cells:
            raise ValueError(f"{self.id}: comb annotations require format.cells")
        return self

    @model_validator(mode="after")
    def _format_keys_apply_to_the_type(self):
        stray = self.format.model_fields_set - FORMAT_KEYS[self.type]
        if stray:
            raise ValueError(
                f"{self.id}: format key(s) {sorted(stray)} have no effect on a "
                f"{self.type!r} field; allowed here: "
                f"{sorted(FORMAT_KEYS[self.type]) or 'none'}")
        return self


class FieldAnnotation(Printable):
    kind: Literal["field"] = "field"
    page: int
    box: Box


class GroupColumn(Printable):
    """A column only declares its horizontal extent: the vertical position of
    every cell comes from the group's firstRowY and rowHeight."""
    x: float
    width: float

    def as_field(self, *, id: str, page: int, box: Box) -> FieldAnnotation:
        kept = self.model_dump(exclude_unset=True, exclude={"id", "x", "width"})
        return FieldAnnotation(**kept, id=id, page=page, box=box)


class GroupAnnotation(BaseModel):
    kind: Literal["group"]
    id: str
    label: str
    page: int
    source: str
    rowHeight: float
    maxRows: int
    firstRowY: float
    columns: list[GroupColumn]
    overflowStrategy: Literal["statement", "error"] = "statement"
    overflowTarget: str | None = None
    condition: Condition | None = None

    def row_box(self, column: GroupColumn, n: int) -> Box:
        return Box(x=column.x, y=self.firstRowY + n * self.rowHeight,
                   width=column.width, height=self.rowHeight)


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


class Defaults(BaseModel):
    """Set-wide fallbacks. An annotation overrides a default by naming the key,
    even when it names the same value the model would have used anyway."""
    style: Style = Field(default_factory=Style)
    format: Format = Field(default_factory=Format)


class AnnotationSet(BaseModel):
    specVersion: Literal["1.0"]
    form: FormMeta
    source: SourceMeta
    pages: list[PageMeta]
    defaults: Defaults = Field(default_factory=Defaults)
    annotations: list[Annotation]

    @model_validator(mode="after")
    def _referential_integrity(self):
        pages = {p.number: p for p in self.pages}
        seen: set[str] = set()
        top_level_field_ids = {a.id for a in self.annotations
                               if isinstance(a, FieldAnnotation)}
        for a in self.annotations:
            if a.page not in pages:
                raise ValueError(f"{a.id}: page {a.page} is not declared in pages[]")
            if a.id in seen:
                raise ValueError(f"duplicate annotation id {a.id!r}")
            seen.add(a.id)
            page = pages[a.page]
            if isinstance(a, FieldAnnotation):
                if not a.box.fits(page):
                    raise ValueError(f"{a.id}: box {a.box.model_dump()} does not fit "
                                     f"on page {a.page} ({page.width}x{page.height})")
            else:
                for c in a.columns:
                    if c.id in seen:
                        raise ValueError(f"duplicate annotation id {c.id!r}")
                    seen.add(c.id)
                    last = a.row_box(c, max(a.maxRows - 1, 0))
                    if not a.row_box(c, 0).fits(page) or not last.fits(page):
                        raise ValueError(
                            f"{a.id}.{c.id}: {a.maxRows} rows of {a.rowHeight}pt from "
                            f"y={a.firstRowY} does not fit on page {a.page} "
                            f"({page.width}x{page.height})")
                if a.overflowStrategy == "statement" and not a.overflowTarget:
                    raise ValueError(
                        f"{a.id}: overflowStrategy 'statement' requires overflowTarget")
                if a.overflowTarget and a.overflowTarget not in top_level_field_ids:
                    raise ValueError(
                        f"{a.id}: overflowTarget {a.overflowTarget!r} does not "
                        "name a top-level field annotation")
        return self
