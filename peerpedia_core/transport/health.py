# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Network reachability -- single function, no dependencies on other sync modules.

``is_online(server_url) -> bool``
    GET /health with a 1.5-second timeout.  Returns True if the server
    responds 200, False on any error (timeout, connection refused, DNS
    failure, non-200 status).  Used by ``cli.py`` to decide whether to
    show sync status or offer push.

    Swallows all exceptions -- the caller just needs a boolean.  This is
    intentional: network detection should never crash the app.

    Results are cached for 30 seconds to avoid repeated timeouts when
    a server is unreachable.
"""

from __future__ import annotations

import time

import httpx

# ── Connection result cache ──────────────────────────────────────────────
# Avoids repeated 1.5s timeouts when a dead server is checked by
# multiple commands in quick succession (e.g. following + followers).
_cache: dict[str, tuple[float, bool]] = {}
_CACHE_TTL = 30.0  # seconds


def clear_health_cache() -> None:
    """Clear the is_online() result cache.  Used by tests that mock httpx."""
    _cache.clear()


def is_online(server_url: str, timeout: float = 1.5) -> bool:
    """Return True if the remote server is reachable.

    All errors (timeout, DNS failure, connection refused, non-200) map to
    ``False``.  This is intentional — the caller only needs a boolean for
    a UI decision (show/hide sync badge), and a failed health check should
    never crash the app.

    Results are cached for 30 seconds to avoid repeated timeouts.

    Args:
        server_url: Base URL of the PeerPedia server (e.g. "https://peerpedia.dev").
        timeout: Request timeout in seconds.
    """
    now = time.time()
    if server_url in _cache:
        cached_time, cached_result = _cache[server_url]
        if now - cached_time < _CACHE_TTL:
            return cached_result

    try:
        response = httpx.get(f"{server_url}/health", timeout=timeout)
        result = response.status_code == 200
    except httpx.HTTPError:
        result = False

    _cache[server_url] = (now, result)
    return result


def check_clock_skew(server_url: str, timeout: float = 1.5) -> int | None:
    """Return the clock skew in seconds (server_time - local_time), or None.

    Positive → local clock is behind the server.
    Negative → local clock is ahead.
    None → server unreachable or missing header.
    """
    try:
        response = httpx.get(f"{server_url}/health", timeout=timeout)
        server_ts = response.headers.get("Server-Time")
        if server_ts:
            return int(server_ts) - int(time.time())
    except (httpx.HTTPError, ValueError):
        pass
    return None
