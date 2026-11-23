"""Deterministic migration routing (requirement 16.1 to 16.5)."""

from __future__ import annotations

from ghost.models import Metrics, Route
from ghost.router.thresholds import RoutingThresholds, load_thresholds


def recommend_route(
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
