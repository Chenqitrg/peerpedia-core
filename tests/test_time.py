# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Time security primitives — replay windows, clock skew."""

import time as _time

from peerpedia_core.time import (
    REPLAY_WINDOW_SECONDS,
    compute_clock_skew,
    validate_clock_skew,
    validate_timestamp,
)


class TestValidateTimestamp:
    def test_valid_timestamp(self):
        now = 1_700_000_000
        ts = now - 10  # within window
        result = validate_timestamp(str(ts), now=now)
        assert result == ts

    def test_timestamp_too_old(self):
        now = 1_700_000_000
        ts = now - REPLAY_WINDOW_SECONDS - 5
        result = validate_timestamp(str(ts), now=now)
        assert isinstance(result, str)
        assert "outside" in result

    def test_timestamp_in_future(self):
        now = 1_700_000_000
        ts = now + REPLAY_WINDOW_SECONDS + 5
        result = validate_timestamp(str(ts), now=now)
        assert isinstance(result, str)
        assert "outside" in result

    def test_timestamp_at_boundary(self):
        """Exactly at the boundary is within window."""
        now = 1_700_000_000
        ts = now - REPLAY_WINDOW_SECONDS
        result = validate_timestamp(str(ts), now=now)
        assert result == ts

    def test_non_integer_timestamp(self):
        result = validate_timestamp("not-a-number")
        assert isinstance(result, str)
        assert "not an integer" in result

    def test_timestamp_defaults_to_current_time(self):
        """Without explicit *now*, uses real time.time()."""
        ts = int(_time.time())
        result = validate_timestamp(str(ts))
        assert isinstance(result, int)  # passes


class TestClockSkew:
    def test_validate_skew_within_window(self):
        assert validate_clock_skew(10) is None
        assert validate_clock_skew(-10) is None

    def test_validate_skew_outside_window(self):
        assert validate_clock_skew(REPLAY_WINDOW_SECONDS + 5) is not None
        assert validate_clock_skew(-(REPLAY_WINDOW_SECONDS + 5)) is not None

    def test_validate_skew_none(self):
        """None skew (unknown) → None (conservative — proceed)."""
        assert validate_clock_skew(None) is None

    def test_compute_clock_skew(self):
        assert compute_clock_skew(100, 90) == 10   # server ahead, local behind
        assert compute_clock_skew(90, 100) == -10  # server behind, local ahead
        assert compute_clock_skew(100, 100) == 0

    def test_replay_window_is_30(self):
        assert REPLAY_WINDOW_SECONDS == 30
