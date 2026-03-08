"""Unified statistics module for EmojiASM."""

from __future__ import annotations

import math
import statistics
from typing import Any


def compute_stats(
    values: list[float | int], histogram_bins: int = 10
) -> dict[str, Any]:
    """Compute descriptive statistics over a list of numeric values.

    NaN and inf values are filtered out before computation.  If all
    values are non-finite, returns the same zero-result as an empty list.

    Args:
        values: List of numeric values (may contain NaN/inf).
        histogram_bins: Number of histogram bins. Set to 0 to skip histogram.

    Returns:
        Dict with keys: mean, std, min, max, count, median, and optionally histogram.
    """
    # Filter out NaN and inf values — they poison arithmetic and comparisons
    values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    count = len(values)

    if count == 0:
        result: dict[str, Any] = {
            "mean": 0,
            "std": 0,
            "min": 0,
            "max": 0,
            "count": 0,
            "median": 0,
        }
        return result

    val_min = min(values)
    val_max = max(values)
    mean = sum(values) / count
    median = statistics.median(values)

    # Population standard deviation
    if count == 1:
        std = 0.0
    else:
        variance = sum((x - mean) ** 2 for x in values) / count
        std = math.sqrt(variance)

    result = {
        "mean": mean,
        "std": std,
        "min": val_min,
        "max": val_max,
        "count": count,
        "median": median,
    }

    if histogram_bins > 0:
        result["histogram"] = _histogram(values, histogram_bins, val_min, val_max)

    return result


def _histogram(
    values: list[float | int], bins: int, val_min: float | int, val_max: float | int
) -> dict[str, list[float]]:
    """Compute histogram edges and counts.

    Returns dict with 'edges' (list of bin edges, length bins+1) and
    'counts' (list of counts per bin, length bins).
    """
    # All same values — single bin
    if val_min == val_max:
        edges = [float(val_min), float(val_min)]
        counts = [len(values)]
        return {"edges": edges, "counts": counts}

    # Compute evenly spaced bin edges
    step = (val_max - val_min) / bins
    edges = [val_min + i * step for i in range(bins)] + [val_max]
    counts = [0] * bins

    for v in values:
        # Find the bin index
        idx = int((v - val_min) / step)
        # Clamp: values equal to val_max go in the last bin
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1

    return {"edges": [float(e) for e in edges], "counts": counts}
