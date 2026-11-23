"""Core data models shared by all Ghost components.

Workbook and Cell are plain dataclasses (they hold sets and are built by the
ingestor). All other models are pydantic models so they serialise to JSON/YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

CellRef = str  # "Sheet!A1"

CellRoleName = Literal["INPUT", "OUTPUT", "INTERMEDIATE", "PARAMETER"]
MismatchClass = Literal[
    "translation bug",
    "original workbook inconsistency",
    "expected by decision",
]
Mode = Literal["faithful", "intended"]
RouteName = Literal["Ghost converts", "AWS Transform custom", "Split"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


class Location(_Model):
    """Source of a comparison or rule: a cell, or a VBA module and line."""

    cell: CellRef | None = None
    module: str | None = None
    line: int | None = None


class VbaModule(_Model):
    name: str
    source: str
    line_count: int


class FeatureFlag(_Model):
    kind: Literal[
        "volatile",
        "external_link",
        "data_table",
        "array_formula",
        "dynamic_array",
        "unsupported_function",
    ]
    cell: CellRef
    detail: str = ""
    # Volatile and external-link cells are reported as "not verifiable as-is".
    not_verifiable: bool = False


@dataclass
class Cell:
    ref: CellRef
    value: int | float | str | bool | None = None
    formula: str | None = None
    saved_value: object | None = None  # Excel-saved result (data_only)
    role: CellRoleName | None = None
    label: str | None = None
    fill: str | None = None
    validation: str | None = None


@dataclass
class Workbook:
    path: str
    sheets: list[str] = field(default_factory=list)
    cells: dict[CellRef, Cell] = field(default_factory=dict)
    named_ranges: dict[str, str] = field(default_factory=dict)
    deps: dict[CellRef, set[CellRef]] = field(default_factory=dict)
    vba_modules: list[VbaModule] = field(default_factory=list)
    features: list[FeatureFlag] = field(default_factory=list)
    excel_saved: bool = False


# --------------------------------------------------------------------------
# Autopsy
# --------------------------------------------------------------------------


class Threshold(_Model):
    cell: CellRef
    operator: str
    constant: Decimal
    source: Location


class Finding(_Model):
    finding_id: str  # F-001
    kind: Literal["operator_conflict"] = "operator_conflict"
    cell: CellRef
    constant: Decimal
    locations: list[tuple[Location, str]]  # location + operator


class Metrics(_Model):
    formula_count: int = 0
    vba_line_count: int = 0
    module_count: int = 0
    userform_count: int = 0
    declare_count: int = 0
    external_link_count: int = 0
    volatile_count: int = 0
    unsupported_count: int = 0
    calculator_shape: bool = False


# --------------------------------------------------------------------------
# Rules, mapping, decisions
# --------------------------------------------------------------------------


class Condition(_Model):
    condition_id: str
    text: str
    cell: CellRef | None = None


class Rule(_Model):
    rule_id: str  # R-xxxxxxxx
    text: str
    cells: list[CellRef] = Field(default_factory=list)
    macro_lines: list[Location] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)


class IOSpec(_Model):
    cell: CellRef
    type: Literal["integer", "decimal", "string", "boolean"] = "decimal"
    min: Decimal | None = None
    max: Decimal | None = None


class Mapping(_Model):
    version: int = 1
    inputs: dict[str, IOSpec] = Field(default_factory=dict)
    outputs: dict[str, IOSpec] = Field(default_factory=dict)


class Decision(_Model):
    decision_id: str  # D-001
    finding_id: str | None = None
    rule_id: str | None = None
    behaviour: str
    reason: str
    author: str
    date: date
    patch: dict[str, Any] = Field(default_factory=dict)  # for Intended mode


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------


class Case(_Model):
    inputs: dict[str, object]
    referee: dict[str, object] = Field(default_factory=dict)
    actual: dict[str, object] = Field(default_factory=dict)


class Mismatch(_Model):
    case: Case
    output: str
    cell: CellRef
    rule_id: str | None = None
    mismatch_class: MismatchClass
    finding_id: str | None = None
    decision_id: str | None = None
    minimal: bool = False


class BoundaryResult(_Model):
    cell: CellRef
    input_name: str
    threshold: Decimal
    change_point: Decimal | None = None
    operator_includes: Literal["at", "above"] | None = None  # which side owns t
    exact_hits: list[dict[str, object]] = Field(default_factory=list)


class RuleCoverage(_Model):
    rule_id: str
    condition_id: str
    seen_true: bool
    seen_false: bool

    @property
    def uncovered(self) -> bool:
        return not (self.seen_true and self.seen_false)


class Mutant(_Model):
    mutant_id: str
    operator: str
    location: str
    killed: bool
    killed_by: Case | None = None
    survivor_reason: str | None = None


class NotChecked(_Model):
    status: Literal["not checked"] = "not checked"


class MutationResult(_Model):
    mutants: list[Mutant]
    killed: int
    total: int

    @property
    def score(self) -> float:
        return self.killed / self.total if self.total else 0.0


class SanityResult(_Model):
    status: Literal["matched", "differences", "not cross-checked against Excel"]
    matched: int = 0
    total: int = 0
    differences: list[dict[str, object]] = Field(default_factory=list)


class Versions(_Model):
    libreoffice: str
    python: str
    ghost: str


class Report(_Model):
    schema_version: str = "1"
    ghost_version: str
    seed: int
    versions: Versions
    mode: Mode
    cases_tested: int
    passed: bool
    mismatches: list[Mismatch] = Field(default_factory=list)
    boundaries: list[BoundaryResult] = Field(default_factory=list)
    rule_coverage: list[RuleCoverage] = Field(default_factory=list)
    mutation: Union[MutationResult, NotChecked] = Field(default_factory=NotChecked)
    sanity: Union[SanityResult, NotChecked] = Field(default_factory=NotChecked)
    findings: list[Finding] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


class Route(_Model):
    route: RouteName
    reasons: list[str]
    metrics: Metrics
    atx_command: str | None = None
