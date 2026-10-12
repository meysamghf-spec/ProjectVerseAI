"""Probability helpers used by the Monte Carlo engine.

Percentiles use the linear method between sorted samples (equivalent to
numpy's percentile with linear interpolation). They are computed only from
the samples of a run. The engine does not invent intervals.
"""

from __future__ import annotations

import math
import random


def validate_triangular(low: float, mode: float, high: float, label: str) -> None:
    if low - mode > 1e-9 or mode - high > 1e-9:
        raise ValueError(
            f"{label} is not a valid triangular distribution (min <= mode <= max required)."
        )
    if high < low:
        raise ValueError(f"{label} has a maximum below its minimum.")


def sample_triangular(rng: random.Random, low: float, mode: float, high: float) -> float:
    validate_triangular(low, mode, high, "Triangular sample")
    if abs(high - low) <= 1e-12:
        return low
    return rng.triangular(low, high, mode)


def percentile(samples: list[float], p: float) -> float:
    """Linear percentile. `p` is on a 0-100 scale."""

    if not samples:
        raise ValueError("Cannot compute a percentile from an empty sample.")
    if p < 0 or p > 100:
        raise ValueError("Percentile must be between 0 and 100.")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x <= 1e-12 or den_y <= 1e-12:
        return 0.0
    return num / (den_x * den_y)
