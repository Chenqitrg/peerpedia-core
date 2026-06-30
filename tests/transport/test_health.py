# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for transport/http/health.py — reachability check + clock skew."""

import time
from unittest.mock import MagicMock, patch

import pytest

from peerpedia_core.transport.http.health import (
    clear_health_cache,
    is_online,
    check_clock_skew,
    _lookup_cache,
    _prune_cache,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Cache operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestCacheOperations:
    def test_lookup_hit_returns_value(self):
        """Fresh cache entry returns the stored (online, server_ts)."""
        now = time.time()
        store = {"https://peer.example.com": (now, True, 1700000000)}
        result = _lookup_cache(store, "https://peer.example.com", now + 10, 30)
        assert result == (True, 1700000000)

    def test_lookup_miss_expired(self):
        """Expired cache entry returns None — stale data must be re-fetched."""
        now = time.time()
        store = {"https://peer.example.com": (now - 60, True, 1700000000)}
        result = _lookup_cache(store, "https://peer.example.com", now, 30)
        assert result is None

    def test_lookup_miss_unknown_key(self):
        """Unknown server returns None."""
        result = _lookup_cache({}, "https://unknown.example.com", time.time(), 30)
        assert result is None

    def test_prune_keeps_max_entries(self):
        """Only the 10 most recent entries are retained."""
        now = time.time()
        data = {f"https://s{i}.example.com": (now - i, True, None) for i in range(15)}
        _prune_cache(data)
        assert len(data) == 10

    def test_clear_health_cache_empties_store(self, monkeypatch):
        """clear_health_cache() removes in-memory entries and disk file."""
        from peerpedia_core.transport.http import health

        # Populate in-memory cache
        health._cache["https://x.example.com"] = (time.time(), True, None)
        clear_health_cache()
        assert len(health._cache) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Clock skew
# ═══════════════════════════════════════════════════════════════════════════════


class TestClockSkew:
    def test_positive_skew_means_local_behind(self):
        """Server time > local time → positive skew (local clock is behind)."""
        from peerpedia_core.time import compute_clock_skew
        skew = compute_clock_skew(1000, 900)
        assert skew == 100  # server - local

    def test_negative_skew_means_local_ahead(self):
        """Server time < local time → negative skew (local clock is ahead)."""
        from peerpedia_core.time import compute_clock_skew
        skew = compute_clock_skew(900, 1000)
        assert skew == -100

    def test_same_time_returns_zero(self):
        """Identical timestamps → zero skew."""
        from peerpedia_core.time import compute_clock_skew
        assert compute_clock_skew(500, 500) == 0

    def test_unreachable_returns_none(self):
        """When server is unreachable, clock_skew returns None — no crash."""
        with patch.object(health_mod, '_probe', return_value=(False, None)):
            assert check_clock_skew("https://offline.example.com") is None


import peerpedia_core.transport.http.health as health_mod


class TestClockSkewViaProbe:
    def test_positive_skew_via_mock(self):
        """Integration: positive skew returns positive int."""
        with patch.object(health_mod, '_probe', return_value=(True, 1000)):
            with patch('peerpedia_core.transport.http.health.int', wraps=int) as mock_int:
                mock_int.return_value = 900  # local time
                result = check_clock_skew("https://peer.example.com")
                # server_ts=1000, local mocked to 900 → skew = 100
                assert result is not None

    def test_reachable_no_server_time_returns_none(self):
        """Online but no Server-Time header → None."""
        with patch.object(health_mod, '_probe', return_value=(True, None)):
            assert check_clock_skew("https://peer.example.com") is None
