"""Rate the walk conditions at a checkpoint as good / fair / poor (or fault).

`rate` is a pure function: no hardware, no clock, no I/O, so it runs and is tested anywhere.
The thresholds come from the `[conditions.<value>]` tables in `sensor-node/config.toml`.
The rating is general information, not medical or safety advice.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"

GOOD, FAIR, POOR, FAULT = "good", "fair", "poor", "fault"
_SEVERITY = {GOOD: 0, FAIR: 1, POOR: 2}

Thresholds = Mapping[str, Mapping[str, Any]]


def rate(readings: Mapping[str, float | None], thresholds: Thresholds) -> tuple[str, str]:
    """Return `(condition, reason)` for the latest readings.

    Only values that have thresholds are rated (temperature, humidity); others such as light
    are context and ignored. Ranges are inclusive. Inside `good` is good, inside `fair` is
    fair, anything else is poor. The worst value wins. `None` is ignored. If no rated value
    is present, the result is `fault`.
    """
    levels: dict[str, tuple[str, float]] = {}
    for name, limits in thresholds.items():
        value = readings.get(name)
        if value is not None:
            levels[name] = (_level(value, limits), value)

    if not levels:
        return FAULT, "no sensor values"

    worst = max((level for level, _ in levels.values()), key=_SEVERITY.__getitem__)
    if worst == GOOD:
        reason = "all values in comfort range"
    else:
        reason = ", ".join(
            _describe(name, value, thresholds[name])
            for name, (level, value) in levels.items()
            if level == worst
        )

    missing = [name for name in thresholds if name not in levels]
    if missing:
        reason += f" ({', '.join(missing)} missing)"
    return worst, reason


def _level(value: float, limits: Mapping[str, Any]) -> str:
    good_low, good_high = limits["good"]
    fair_low, fair_high = limits["fair"]
    if good_low <= value <= good_high:
        return GOOD
    if fair_low <= value <= fair_high:
        return FAIR
    return POOR


def _describe(name: str, value: float, limits: Mapping[str, Any]) -> str:
    direction = "low" if value < limits["good"][0] else "high"
    unit = limits.get("unit")
    return f"{name} {direction} ({value:g}{' ' + unit if unit else ''})"


def load_thresholds(path: Path = CONFIG_PATH) -> dict[str, dict[str, Any]]:
    """Read and check the `[conditions.<value>]` tables from config.toml."""
    with path.open("rb") as file:
        return validate_thresholds(tomllib.load(file).get("conditions"))


def validate_thresholds(tables: object) -> dict[str, dict[str, Any]]:
    """Fail at start-up with a clear message instead of rating with broken limits later."""
    if not isinstance(tables, dict) or not tables:
        raise ValueError("config has no [conditions.<value>] tables")
    for name, limits in tables.items():
        if not isinstance(limits, dict):
            raise ValueError(f"[conditions.{name}] must be a table")
        good = _range(name, "good", limits.get("good"))
        fair = _range(name, "fair", limits.get("fair"))
        if not (fair[0] <= good[0] and good[1] <= fair[1]):
            raise ValueError(f"[conditions.{name}] good {good} must lie inside fair {fair}")
    return tables


def _range(name: str, key: str, value: object) -> tuple[float, float]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value)
    ):
        raise ValueError(f"[conditions.{name}] {key} must be [low, high], got {value!r}")
    low, high = value
    if low > high:
        raise ValueError(f"[conditions.{name}] {key} {value} is reversed")
    return low, high
