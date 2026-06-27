# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Time security primitives — replay windows, clock skew.  Pure logic, zero IO.

PeerPedia uses timestamps as a security boundary:
- Auth headers carry a Unix timestamp; the server rejects requests >30s old.
- Git bundle sync requires client and server clocks to agree within 30s,
  because commit timestamps determine priority in conflict resolution.

The 30-second window is a protocol constant, not a config knob.  It balances
clock drift tolerance against replay-attack surface.
"""

from __future__ import annotations

import time as _time

REPLAY_WINDOW_SECONDS: int = 30
"""Maximum allowed skew between client and server clocks (seconds).

Both auth replay protection and bundle sync clock-skew checks use this
same value.  It is intentionally not in ``config/params.py`` — changing
it would break the protocol between peers.
"""


def validate_clock_skew(skew_seconds: int | None, *,
                        window: int = REPLAY_WINDOW_SECONDS) -> str | None:
    """Check a clock-skew measurement against the protocol window.

    Returns an error description string if the clocks are too far apart,
    or ``None`` if the skew is acceptable or unknown.
    """
    if skew_seconds is None:
        return None
    if abs(skew_seconds) > window:
        direction = "behind" if skew_seconds > 0 else "ahead"
        return f"Clock is {abs(skew_seconds)}s {direction} the server"
    return None


def validate_timestamp(ts_str: str, *, now: int | None = None,
                       window: int = REPLAY_WINDOW_SECONDS) -> int | str:
    """Parse *ts_str* as a Unix timestamp and check the replay window.

    Returns the parsed timestamp on success, or an error string on failure.
    *now* defaults to ``int(time.time())``; pass it explicitly in tests.
    """
    try:
        ts = int(ts_str)
    except ValueError:
        return f"Timestamp '{ts_str}' is not an integer"
    if now is None:
        now = int(_time.time())
    if abs(now - ts) > window:
        return f"Timestamp {ts} is outside ±{window}s window (server time: {now})"
    return ts
