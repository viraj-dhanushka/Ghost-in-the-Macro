"""Deterministic migration routing (requirement 16.1 to 16.5)."""

from __future__ import annotations

from ghost.ingest.limits import MAX_CELLS, MAX_FILE_BYTES, MAX_FORMULAS
from ghost.ingest.triage import SizeProfile
from ghost.models import Metrics, Route
from ghost.router.thresholds import RoutingThresholds, load_thresholds

__all__ = ["over_limits", "recommend_route", "route_for_sizes", "route_workbook"]

_AWS_NOW = "goes to AWS Transform custom (suggested command, not run)"


def _vba_part(route: str, m: Metrics, error: str | None = None, present: bool | None = None) -> str:
    if error:
        return "VBA: not readable"
    if m.vba_line_count == 0 and not present:
        return "VBA: none"
    if route in ("AWS Transform custom", "Split"):
        return f"VBA: {m.vba_line_count} lines, {_AWS_NOW}"
    return f"VBA: {m.vba_line_count} lines, read statically, not converted by Ghost"


def _recommend(
    metrics: Metrics,
    batch_size: int = 1,
    thresholds: RoutingThresholds | None = None,
) -> Route:
    """Return exactly one Route for the given metrics and batch size.

    Precedence: batch size, then UserForm or Declare counts above their
    thresholds (all "AWS Transform custom"); then large VBA, which is "Split"
    when the workbook also has formulas and "AWS Transform custom" otherwise;
    everything else is "Ghost converts".
    """
    t = thresholds if thresholds is not None else load_thresholds()
    aws: list[str] = []

    if batch_size >= t.batch_size_threshold:
        aws.append(
            f"batch of {batch_size} workbooks is at or above the batch threshold "
            f"of {t.batch_size_threshold}"
        )
    if metrics.userform_count > t.userform_threshold:
        aws.append(
            f"{metrics.userform_count} UserForms exceed the threshold of {t.userform_threshold}"
        )
    if metrics.declare_count > t.declare_threshold:
        aws.append(
            f"{metrics.declare_count} Windows API Declares exceed the threshold "
            f"of {t.declare_threshold}"
        )
    large_vba = metrics.vba_line_count > t.vba_line_threshold
    vba_reason = (
        f"{metrics.vba_line_count} VBA lines exceed the threshold of {t.vba_line_threshold}"
    )

    if aws:
        if large_vba:
            aws.append(vba_reason)
        return Route(route="AWS Transform custom", reasons=aws, metrics=metrics)

    if large_vba:
        if metrics.formula_count > 0:
            return Route(
                route="Split",
                reasons=[
                    vba_reason,
                    f"{metrics.formula_count} formulas can be converted by Ghost; "
                    "the VBA goes to AWS Transform custom",
                ],
                metrics=metrics,
            )
        return Route(
            route="AWS Transform custom",
            reasons=[vba_reason, "no formulas for Ghost to convert"],
            metrics=metrics,
        )

    reasons = [
        f"{metrics.vba_line_count} VBA lines are within the threshold of {t.vba_line_threshold}",
        "UserForm and Declare counts are within their thresholds",
        f"batch size {batch_size} is below {t.batch_size_threshold}",
    ]
    return Route(route="Ghost converts", reasons=reasons, metrics=metrics)


def recommend_route(
    metrics: Metrics,
    batch_size: int = 1,
    thresholds: RoutingThresholds | None = None,
) -> Route:
    """Return exactly one Route for the metrics of a loaded workbook, with the part sentences added."""
    route = _recommend(metrics, batch_size, thresholds)
    parts = [
        _vba_part(route.route, metrics),
        f"Formulas: {metrics.formula_count:,}, not sent, converted by Ghost "
        "(supported functions only; the rest are listed as not converted)",
    ]
    return route.model_copy(update={"parts": parts})


def _limit_reasons(s: SizeProfile, t: RoutingThresholds) -> list[str]:
    """Every limit exceeded, and anything that could not be counted, in words with the measured number."""
    mb, mc, mf = min(t.max_file_bytes, MAX_FILE_BYTES), min(t.max_cells, MAX_CELLS), min(t.max_formulas, MAX_FORMULAS)
    out = []
    if s.file_bytes > mb:
        out.append(f"file is {s.file_bytes:,} bytes; the limit is {mb:,} bytes")
    if s.cells is not None and s.cells > mc:
        out.append(f"{'at least ' if not s.counted else ''}{s.cells:,} cells; the limit is {mc:,} cells")
    if s.formulas is not None and s.formulas > mf:
        out.append(f"{'at least ' if not s.counted else ''}{s.formulas:,} formulas; the limit is {mf:,} formulas")
    if s.not_counted_reason:
        out.append(s.not_counted_reason)
    return out


def over_limits(s: SizeProfile, t: RoutingThresholds) -> bool:
    """True when the workbook is over a limit, or its size could not be established (then it cannot be loaded)."""
    return bool(_limit_reasons(s, t)) or not s.counted or s.cells is None or s.formulas is None


def route_workbook(path, batch_size: int = 1, thresholds: RoutingThresholds | None = None, load=None) -> Route:
    """Triage first, then route. A workbook over a limit is routed from its measured sizes and is never loaded;
    any other workbook is loaded with ``load(path)`` and routed from its metrics, exactly as before.
    ``load`` is the front end's own loader (it runs the feature scan)."""
    from pathlib import Path

    from ghost.ingest.limits import ACCEPTED_FORMATS
    from ghost.ingest.triage import scan_sizes

    t = thresholds if thresholds is not None else load_thresholds()
    if str(path).lower().endswith(ACCEPTED_FORMATS) and Path(path).is_file():
        sizes = scan_sizes(path)
        if over_limits(sizes, t):
            return route_for_sizes(sizes, t, batch_size)
    from ghost.autopsy.metrics import metrics as compute_metrics

    if load is None:
        from ghost.ingest.workbook import load_workbook as load
    wb = load(str(path))
    route = recommend_route(compute_metrics(wb), batch_size, t)
    # The loaded workbook knows whether its VBA could be read: never say "none" for VBA that is there but unreadable.
    parts = [_vba_part(route.route, route.metrics, getattr(wb, "vba_error", None), getattr(wb, "vba_present", None))]
    return route.model_copy(update={"parts": parts + route.parts[1:]})


def route_for_sizes(s: SizeProfile, thresholds: RoutingThresholds | None = None, batch_size: int = 1) -> Route:
    """The route for a workbook that was measured but not loaded. Exactly one route; every limit exceeded and
    everything that could not be counted is in the reasons. A workbook that is within every limit gets the
    ordinary route from its measured figures."""
    t = thresholds if thresholds is not None else load_thresholds()
    metrics = Metrics(
        formula_count=s.formulas or 0,
        vba_line_count=s.vba_lines,
        module_count=s.vba_modules,
        userform_count=s.userforms,
        declare_count=s.declares,
    )
    size_reasons = _limit_reasons(s, t)
    if not over_limits(s, t):
        base = recommend_route(metrics, batch_size, t)
        return base.model_copy(update={"parts": [_vba_part(base.route, metrics, s.vba_error, s.vba_present), base.parts[1]]})
    core = _recommend(metrics, batch_size, t)
    vba_goes = core.route in ("AWS Transform custom", "Split")
    if vba_goes:
        route = "AWS Transform custom"
        reasons = list(core.reasons) if core.route == "AWS Transform custom" else [core.reasons[0]]
        reasons = [r for r in reasons if "can be converted by Ghost" not in r and "no formulas" not in r]
        reasons += size_reasons
        reasons.append("the formulas are not sent to AWS Transform and Ghost does not convert them at this size")
    else:
        route = "Over Ghost's limits"
        reasons = size_reasons or ["the workbook could not be measured within Ghost's limits"]
        reasons.append("Ghost does not convert or verify a workbook over its limits here; run it on a smaller copy")
    if s.formulas is None:
        formulas = "Formulas: not counted"
    elif not s.counted:
        formulas = f"Formulas: not counted (at least {s.formulas:,} seen)"
    else:
        formulas = f"Formulas: {s.formulas:,}, not sent, not converted by Ghost (over the limit)"
    parts = [
        _vba_part(route, metrics, s.vba_error, s.vba_present),
        formulas,
        "Not checked (the workbook was not loaded): calculator shape, external links, volatile and unsupported constructs.",
    ]
    return Route(route=route, reasons=reasons, metrics=metrics, parts=parts)
