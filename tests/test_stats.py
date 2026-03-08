"""Tests for the unified stats module."""

import math

import pytest

from emojiasm.stats import compute_stats


def test_empty_list():
    """compute_stats([]) returns zeros/defaults."""
    r = compute_stats([])
    assert r["mean"] == 0
    assert r["std"] == 0
    assert r["min"] == 0
    assert r["max"] == 0
    assert r["count"] == 0
    assert r["median"] == 0
    assert "histogram" not in r  # default bins=10 but no data


def test_single_value():
    """compute_stats([5]) returns mean=5, std=0, median=5."""
    r = compute_stats([5])
    assert r["mean"] == 5
    assert r["std"] == 0
    assert r["median"] == 5
    assert r["min"] == 5
    assert r["max"] == 5
    assert r["count"] == 1


def test_basic_stats():
    """compute_stats([1,2,3,4,5]) returns correct mean, std, min, max, count, median."""
    r = compute_stats([1, 2, 3, 4, 5])
    assert r["count"] == 5
    assert r["mean"] == 3.0
    assert r["median"] == 3
    assert r["min"] == 1
    assert r["max"] == 5
    # Population std of [1,2,3,4,5]: sqrt(2)
    assert abs(r["std"] - math.sqrt(2)) < 1e-9


def test_median_even_count():
    """Even number of values returns correct median (average of two middle)."""
    r = compute_stats([1, 2, 3, 4])
    # statistics.median([1,2,3,4]) == 2.5
    assert r["median"] == 2.5
    assert r["count"] == 4


def test_histogram_bin_counts():
    """Histogram counts sum to total count."""
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    r = compute_stats(values, histogram_bins=5)
    hist = r["histogram"]
    assert sum(hist["counts"]) == len(values)
    assert len(hist["counts"]) == 5
    assert len(hist["edges"]) == 6  # bins + 1


def test_histogram_edges_monotonic():
    """Histogram edges are strictly increasing."""
    r = compute_stats([1, 5, 10, 15, 20], histogram_bins=4)
    edges = r["histogram"]["edges"]
    for i in range(len(edges) - 1):
        assert edges[i] < edges[i + 1], f"edges[{i}]={edges[i]} >= edges[{i+1}]={edges[i+1]}"


def test_nan_inf_handling():
    """Values with NaN/inf are filtered out gracefully."""
    values = [1, 2, float("nan"), 3, float("inf"), float("-inf"), 4, 5]
    r = compute_stats(values)
    # Only finite values: [1, 2, 3, 4, 5]
    assert r["count"] == 5
    assert r["mean"] == 3.0
    assert r["median"] == 3
    assert r["min"] == 1
    assert r["max"] == 5


def test_all_same_values():
    """All identical values don't crash histogram."""
    r = compute_stats([7, 7, 7, 7, 7], histogram_bins=10)
    assert r["mean"] == 7
    assert r["std"] == 0
    assert r["median"] == 7
    hist = r["histogram"]
    assert sum(hist["counts"]) == 5
    # All same => single bin with all values
    assert hist["counts"] == [5]
    assert len(hist["edges"]) == 2
    assert hist["edges"][0] == 7.0
    assert hist["edges"][1] == 7.0


def test_no_histogram():
    """histogram_bins=0 skips histogram in result."""
    r = compute_stats([1, 2, 3, 4, 5], histogram_bins=0)
    assert "histogram" not in r
    assert r["count"] == 5
    assert r["mean"] == 3.0
