"""Routing thresholds parsed from the fenced YAML block in routing-thresholds.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FENCE = re.compile(r"```ya?ml\s*\n(.*?)\n```", re.DOTALL)
_KEYS = (
    "vba_line_threshold",
    "userform_threshold",
    "declare_threshold",
    "batch_size_threshold",
)


class ThresholdError(ValueError):
    """The thresholds file is missing, malformed or has invalid values."""


@dataclass(frozen=True)
class RoutingThresholds:
    vba_line_threshold: int = 2000
    userform_threshold: int = 3
    declare_threshold: int = 5
    batch_size_threshold: int = 10
    version: int = 1


DEFAULT_THRESHOLDS = RoutingThresholds()


def default_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".kiro" / "steering" / "routing-thresholds.md"


def parse_thresholds(text: str) -> RoutingThresholds:
    """Parse the first fenced YAML block containing ``routing_thresholds``."""
    for match in _FENCE.finditer(text):
        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            raise ThresholdError(f"invalid YAML in routing thresholds: {exc}") from exc
        if isinstance(data, dict) and "routing_thresholds" in data:
            block = data["routing_thresholds"]
            if not isinstance(block, dict):
                raise ThresholdError("routing_thresholds must be a mapping")
            values: dict[str, int] = {}
            for key in _KEYS:
                if key not in block:
                    raise ThresholdError(f"missing key: {key}")
                value = block[key]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ThresholdError(f"{key} must be a non-negative integer")
                values[key] = value
            version = block.get("version", 1)
            if isinstance(version, bool) or not isinstance(version, int):
                raise ThresholdError("version must be an integer")
            return RoutingThresholds(version=version, **values)
    raise ThresholdError("no fenced YAML block with routing_thresholds found")


def load_thresholds(path: str | Path | None = None) -> RoutingThresholds:
    """Load thresholds from ``path`` (default: the steering file)."""
    p = Path(path) if path is not None else default_path()
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ThresholdError(f"cannot read {p}: {exc}") from exc
    return parse_thresholds(text)
