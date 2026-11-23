"""Mutant generation for the mutation self-check (P1, Requirement 9.1).

``generate_mutants`` takes the source (or ``ast.Module``) of a generated
``logic.py`` and returns one mutant per applicable site. Operators:

* ``flip_comparison``   ``xl_ge`` <-> ``xl_gt`` and ``xl_le`` <-> ``xl_lt``
* ``constant_plus_one`` / ``constant_minus_one``  numeric literals
* ``rounding_mode``     ``xl_round`` (half away from zero) -> half even
* ``drop_if_then`` / ``drop_if_else``  an IF collapses to one branch

Output is deterministic: the same source yields the same mutants and ids.
Mutants identical to the source (after normalisation) are never returned.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ghost.models import Mutant

FLIPS = {"xl_ge": "xl_gt", "xl_gt": "xl_ge", "xl_le": "xl_lt", "xl_lt": "xl_le"}

HALF_EVEN_HELPER = "_mut_round_half_even"

_HALF_EVEN_SOURCE = '''
def _mut_round_half_even(x, n=0):
    from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Context, localcontext
    v = xl_num(x)
    if isinstance(v, ExcelError):
        return v
    k = xl_num(n)
    if isinstance(k, ExcelError):
        return k
    k = int(k.to_integral_value(rounding=ROUND_DOWN))
    with localcontext(Context(prec=60)):
        v = Context(prec=15).create_decimal(v)
        if v == 0:
            return Decimal(0)
        return v.quantize(Decimal(1).scaleb(-k), rounding=ROUND_HALF_EVEN)
'''


@dataclass(frozen=True)
class GeneratedMutant:
    mutant_id: str
    operator: str
    location: str  # cell key such as "Sheet1!B5", or "_CONSTS[...]"
    description: str
    source: str  # complete mutated module source

    def to_model(self) -> Mutant:
        """Unverified ``Mutant`` record (``killed`` is set by the runner)."""
        return Mutant(
            mutant_id=self.mutant_id,
            operator=self.operator,
            location=self.location,
            killed=False,
        )


@dataclass
class _Site:
    index: int
    operator: str
    location: str
    description: str


def _numeric_str(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    try:
        return Decimal(node.value).is_finite()
    except InvalidOperation:
        return False


def _is_decimal_literal(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Decimal"
        and len(node.args) == 1
        and not node.keywords
        and _numeric_str(node.args[0])
    )


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _scopes(tree: ast.Module):
    """Yield (location, node) for every ``_CONSTS`` entry and compute() cell."""
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_CONSTS" for t in stmt.targets)
            and isinstance(stmt.value, ast.Dict)
        ):
            for key, val in zip(stmt.value.keys, stmt.value.values):
                name = key.value if isinstance(key, ast.Constant) else "?"
                yield str(name), val
        elif isinstance(stmt, ast.FunctionDef) and stmt.name == "compute":
            for inner in stmt.body:
                if (
                    isinstance(inner, ast.Assign)
                    and len(inner.targets) == 1
                    and isinstance(inner.targets[0], ast.Subscript)
                    and isinstance(inner.targets[0].slice, ast.Constant)
                    and _call_name(inner.value) != "_inp"
                    and _is_assignment_from_formula(inner)
                ):
                    yield str(inner.targets[0].slice.value), inner.value


def _is_assignment_from_formula(stmt: ast.Assign) -> bool:
    # ``v = dict(_CONSTS)`` is a Name target; input bindings use _inp.
    return isinstance(stmt.targets[0].value, ast.Name) and stmt.targets[0].value.id == "v"


class _Visitor(ast.NodeTransformer):
    """Counts mutation sites; applies the one whose index equals ``target``."""

    def __init__(self, target: int | None = None):
        self.target = target
        self.counter = 0
        self.sites: list[_Site] = []
        self.location = ""
        self.applied = False

    def _hit(self, operator: str, description: str) -> bool:
        idx = self.counter
        self.counter += 1
        self.sites.append(_Site(idx, operator, self.location, description))
        return self.target == idx

    def visit_Call(self, node: ast.Call):  # noqa: N802
        name = _call_name(node)
        if _is_decimal_literal(node):
            text = node.args[0].value  # type: ignore[attr-defined]
            for op, delta in (("constant_plus_one", 1), ("constant_minus_one", -1)):
                if self._hit(op, f"constant {text} -> {Decimal(text) + delta}"):
                    new = Decimal(text) + delta
                    node.args[0] = ast.Constant(value=format(new, "f"))
                    self.applied = True
            return node
        if name in FLIPS:
            if self._hit("flip_comparison", f"{name} -> {FLIPS[name]}"):
                node.func.id = FLIPS[name]  # type: ignore[union-attr]
                self.applied = True
        elif name == "xl_round":
            if self._hit("rounding_mode", "ROUND half up -> half even"):
                node.func.id = HALF_EVEN_HELPER  # type: ignore[union-attr]
                self.applied = True
        elif name == "_if" and len(node.args) == 5:
            for op, pos, label in (("drop_if_then", 3, "THEN"), ("drop_if_else", 4, "ELSE")):
                if self._hit(op, f"IF keeps only the {label} branch"):
                    branch = node.args[pos]
                    if isinstance(branch, ast.Lambda):
                        self.applied = True
                        return branch.body
        self.generic_visit(node)
        return node

    def run(self, tree: ast.Module) -> None:
        for location, node in list(_scopes(tree)):
            self.location = location
            replaced = self.visit(node)
            if replaced is not node:  # top-level node replaced: patch the parent
                _replace_top(tree, node, replaced)


def _replace_top(tree: ast.Module, old: ast.AST, new: ast.AST) -> None:
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and n.value is old:
            n.value = new
            return
        if isinstance(n, ast.Dict):
            for i, v in enumerate(n.values):
                if v is old:
                    n.values[i] = new
                    return


def _normalise(tree: ast.Module) -> str:
    return ast.unparse(ast.fix_missing_locations(tree))


def generate_mutants(module: str | ast.Module) -> list[GeneratedMutant]:
    """Return every distinct mutant of a generated module, in stable order."""
    source = module if isinstance(module, str) else ast.unparse(module)
    original = _normalise(ast.parse(source))

    probe = _Visitor()
    probe.run(ast.parse(source))
    sites = probe.sites

    helper = ast.parse(_HALF_EVEN_SOURCE).body
    out: list[GeneratedMutant] = []
    seen = {original}
    ordinal: dict[tuple[str, str], int] = {}
    for site in sites:
        tree = ast.parse(source)
        visitor = _Visitor(target=site.index)
        visitor.run(tree)
        if not visitor.applied:
            continue
        if site.operator == "rounding_mode":
            tree.body.extend(helper)
        text = _normalise(tree)
        if text in seen:
            continue
        seen.add(text)
        key = (site.operator, site.location)
        n = ordinal.get(key, 0)
        ordinal[key] = n + 1
        digest = hashlib.sha1(f"{site.operator}|{site.location}|{n}".encode()).hexdigest()[:8]
        out.append(
            GeneratedMutant(
                mutant_id=f"M-{digest}",
                operator=site.operator,
                location=site.location,
                description=site.description,
                source=text + "\n",
            )
        )
    return out
