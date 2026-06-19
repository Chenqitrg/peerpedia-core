# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for search_monotonic_boundary — the abstract k-exponential + binary
refinement algorithm in monotonic_search.py.

These tests are pure math — no git, no HTTP, no filesystem.  The probe
callback is a simple lookup into a ``list[bool]``.
"""

import pytest
from peerpedia_core.sync.monotonic_search import search_monotonic_boundary


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_probe(truth: list[bool | None]):
    """Return a probe_at closure that reads from *truth*.

    *truth[i]* is the answer for index *i*.

    Also tracks how many times the probe was called so tests can assert
    O(log n) probe counts.
    """
    calls = [0]

    def probe_at(index: int) -> bool | None:
        calls[0] += 1
        if index < 0 or index >= len(truth):
            raise IndexError(f"probe_at({index}) out of range [0, {len(truth) - 1}]")
        return truth[index]

    return probe_at, calls


def _make_truth(n: int, first_true: int) -> list[bool]:
    """Build a truth list of length *n* where indices >= *first_true* are True."""
    return [i >= first_true for i in range(n)]


# ── Happy path ────────────────────────────────────────────────────────────────


class TestHappyPath:
    """Correct boundary detection in typical scenarios."""

    def test_boundary_at_zero(self):
        """probe_at(0) = True → return 0 immediately (one probe)."""
        truth = _make_truth(10, 0)
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result == 0
        assert calls[0] == 1  # single probe

    def test_boundary_at_k(self):
        """Boundary exactly at a k-exponential probe point (dist=5, k=5)."""
        truth = _make_truth(10, 5)
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result == 5
        # Phase 0: probe(0)=False; Phase 1: probe(1)=False, probe(5)=True
        # Phase 2: binary in (1,5] → probe(3)=False, probe(4)=False
        #   lo=4, hi=5, hi-lo=1 → done
        assert calls[0] == 5  # 0, 1, 5, 3, 4

    def test_boundary_between_probe_points(self):
        """Boundary at dist=3 — binary refinement finds exact match."""
        truth = _make_truth(10, 3)
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result == 3

    def test_boundary_at_last(self):
        """Boundary at the deepest (last) index."""
        n = 10
        truth = _make_truth(n, n - 1)  # only the oldest commit is True
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, n - 1)
        assert result == n - 1

    def test_all_false(self):
        """No True in the entire sequence → None."""
        truth = [False] * 10
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result is None

    def test_all_true(self):
        """All elements True → return 0 (single probe)."""
        truth = [True] * 10
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result == 0
        assert calls[0] == 1


# ── Single-element boundary ───────────────────────────────────────────────────


class TestSingleElement:
    """max_index = 0 — the sequence has exactly one element."""

    def test_single_true(self):
        truth = [True]
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, 0)
        assert result == 0
        assert calls[0] == 1

    def test_single_false(self):
        truth = [False]
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, 0)
        assert result is None

    def test_single_none(self):
        truth = [None]
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, 0)
        assert result is None
        assert calls[0] == 1


# ── Deep boundary (k-exponential overshoot) ───────────────────────────────────


class TestDeepBoundary:
    """Boundary is far from index 0 — exercises k-exponential jump + deepest-check."""

    def test_deep_within_range(self):
        """Boundary at dist=150 within 200-element sequence."""
        n = 200
        truth = _make_truth(n, 150)
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, n - 1)
        assert result == 150

        # Probe count should be O(log n), not O(n)
        assert calls[0] < 30  # generous upper bound; actual ≈ 15

    def test_deep_within_range_high_k(self):
        """k=2: boundary at dist=128 in a 200-element sequence."""
        n = 200
        truth = _make_truth(n, 128)
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, n - 1, k=2)
        assert result == 128

    def test_deep_between_last_probe_and_end(self):
        """Boundary between the last k-exponential probe and max_index.

        With k=5, n=10: probes at 1, 5 → 5 is False, next probe 25 > 9 → break.
        Check deepest (9) → True → boundary found at index between 5 and 9.
        """
        truth = _make_truth(10, 8)  # True starts at 8
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, 9)
        assert result == 8


# ── None handling (probe failure mid-search) ─────────────────────────────────


class TestProbeFailure:
    """probe_at returns None — search must abort and return None."""

    def test_none_at_first_probe(self):
        """probe_at(0) = None → immediate abort."""
        truth = [None] + [True] * 9
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result is None
        assert calls[0] == 1  # aborts immediately

    def test_none_during_phase1(self):
        """Probe returns None during k-exponential phase."""
        # Phase 0: probe(0)=False; Phase 1: probe(1)=None
        truth = [False, None] + [True] * 8
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result is None

    def test_none_during_phase2(self):
        """Probe returns None during binary refinement."""
        # Boundary at 2: probe(0)=False, probe(1)=False, probe(5)=True → binary
        # probe(3)=None → abort
        truth = [False, False, True, None, True, True, True, True, True, True]
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, len(truth) - 1)
        assert result is None

    def test_none_at_deepest_check(self):
        """All k-exponential probes False, then deepest check returns None."""
        n = 6
        truth = [False] * n
        truth[-1] = None  # deepest check fails
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, n - 1)
        assert result is None


# ── O(log n) probe count ────────────────────────────────────────────────────


class TestProbeCount:
    """The algorithm must use O(log n) probes, not O(n)."""

    def test_log_probe_count_shallow(self):
        """1000 elements, boundary at 500 → probe count ≪ 1000."""
        n = 1000
        truth = _make_truth(n, 500)
        probe, calls = _mock_probe(truth)

        search_monotonic_boundary(probe, n - 1)
        assert calls[0] < 50  # ~log_5(1000) + log_2(500) ≈ 5 + 9 ≈ 14

    def test_log_probe_count_deep(self):
        """1000 elements, boundary at 999 → still O(log n)."""
        n = 1000
        truth = _make_truth(n, 999)
        probe, calls = _mock_probe(truth)

        search_monotonic_boundary(probe, n - 1)
        assert calls[0] < 50

    def test_log_probe_count_all_false(self):
        """Worst case: all False → one probe per k-step + deepest check."""
        n = 10000
        truth = [False] * n
        probe, calls = _mock_probe(truth)

        search_monotonic_boundary(probe, n - 1)
        # k-exponential probes + deepest check → O(log_k n)
        assert calls[0] < 60

    def test_log_probe_count_all_true(self):
        """Best case: all True → 1 probe."""
        n = 10000
        truth = [True] * n
        probe, calls = _mock_probe(truth)

        search_monotonic_boundary(probe, n - 1)
        assert calls[0] == 1


# ── Custom k ─────────────────────────────────────────────────────────────────


class TestCustomK:
    """Tests with different k values."""

    @pytest.mark.parametrize("k", [2, 3, 5, 10])
    def test_various_k_values(self, k):
        """Boundary detection works for different k values."""
        truth = _make_truth(50, 20)
        probe, _ = _mock_probe(truth)

        result = search_monotonic_boundary(probe, 49, k=k)
        assert result == 20

    def test_k1_raises(self):
        """k=1 is degenerate (1^i = 1 always) — must raise ValueError."""
        truth = _make_truth(20, 15)
        probe, _ = _mock_probe(truth)

        with pytest.raises(ValueError, match="k must be >= 2"):
            search_monotonic_boundary(probe, 19, k=1)


# ── Large max_index (stress test) ────────────────────────────────────────────


class TestLargeMaxIndex:
    """Large sequences don't break the algorithm."""

    def test_large_sequence_all_false(self):
        """max_index = 100000, all False — should complete quickly."""
        n = 100000
        # Build truth lazily to keep the instance small
        truth = [False] * n
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, n - 1)
        assert result is None
        assert calls[0] < 80  # log_5(100k) ≈ 8 probes + deepest

    def test_large_sequence_all_true(self):
        """max_index = 100000, all True — one probe, instant."""
        n = 100000
        truth = [True] * n
        probe, calls = _mock_probe(truth)

        result = search_monotonic_boundary(probe, n - 1)
        assert result == 0
        assert calls[0] == 1
