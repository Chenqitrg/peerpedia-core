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
    a server is unreachable.  The cache is written to disk so it survives
    across CLI invocations — the first call to a dead server pays the
    1.5s timeout; subsequent calls (any process) return instantly.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path

from peerpedia_core.config.paths import DATA_ROOT as _DATA_ROOT
from peerpedia_core.exceptions import TransportError
from peerpedia_core.time import HEALTH_CACHE_SECONDS, compute_clock_skew
from peerpedia_core.transport.http._core import _api_path, _call

logger = logging.getLogger(__name__)

# ── Connection result cache ──────────────────────────────────────────────
# Two-tier: in-memory (fast, same-process) + file (survives across CLI runs).

# In-memory cache — same process, zero disk I/O.
# Format: (timestamp, online, server_ts_or_none)
_cache: dict[str, tuple[float, bool, int | None]] = {}

# File cache — cross-process.  Stored as {url: [timestamp, online, server_ts]}.
_CACHE_FILE = _DATA_ROOT / "server_health.json"
_MAX_CACHE_ENTRIES = 10  # prevent unbounded growth

def _read_file_cache() -> dict[str, tuple[float, bool, int | None]]:
    """Read health cache from disk.  Returns {} on any error."""
    try:
        raw = json.loads(_CACHE_FILE.read_text())
        return {
            k: (float(v[0]), bool(v[1]), int(v[2]) if v[2] is not None else None)
            for k, v in raw.items()
        }
    except (OSError, json.JSONDecodeError, ValueError, KeyError, IndexError):
        logger.debug("Health cache read error for %s", _CACHE_FILE, exc_info=True)
    return {}


def _write_file_cache(data: dict[str, tuple[float, bool, int | None]]) -> None:
    """Write health cache to disk atomically (best-effort, never raises)."""
    try:
        _DATA_ROOT.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps({k: [v[0], v[1], v[2]] for k, v in data.items()})
        # Write to temp file first, then atomically replace — crash-safe.
        tmp = _DATA_ROOT / ".server_health.tmp"
        tmp.write_text(serialized)
        os.replace(tmp, _CACHE_FILE)
    except OSError:
        logger.debug("Health cache write error for %s", _CACHE_FILE, exc_info=True)


def clear_health_cache() -> None:
    """Clear both in-memory and on-disk health caches.  Used by tests."""
    _cache.clear()
    try:
        _CACHE_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _probe(server_url: str, timeout: float = 1.5) -> tuple[bool, int | None]:
    """HTTP GET /health, cached in memory and on disk.  Returns ``(online, server_ts)``."""
    now = time.time()
    ttl = HEALTH_CACHE_SECONDS + random.uniform(-1.0, 1.0)

    # ── Check caches ────────────────────────────────────────────────────────
    cached = _check_health_cache(server_url, now, ttl)
    if cached is not None:
        return cached

    # ── Probe ───────────────────────────────────────────────────────────────
    online, server_ts = _fetch_health(server_url, timeout)

    # ── Persist ─────────────────────────────────────────────────────────────
    _write_health_cache(server_url, now, online, server_ts)

    return online, server_ts


def _check_health_cache(
    server_url: str, now: float, ttl: float,
) -> tuple[bool, int | None] | None:
    """Return ``(online, server_ts)`` if cached and fresh, else ``None``."""
    result = _lookup_cache(_cache, server_url, now, ttl)
    if result is not None:
        return result
    file_cache = _read_file_cache()
    result = _lookup_cache(file_cache, server_url, now, ttl)
    if result is not None:
        _cache[server_url] = file_cache[server_url]
        return result
    return None


def _lookup_cache(
    store: dict[str, tuple[float, bool, int | None]],
    server_url: str, now: float, ttl: float,
) -> tuple[bool, int | None] | None:
    """Return ``(online, server_ts)`` if *store* has a fresh entry, else ``None``."""
    if server_url not in store:
        return None
    cached_time, cached_online, cached_ts = store[server_url]
    if now - cached_time < ttl:
        return cached_online, cached_ts
    return None


def _fetch_health(server_url: str, timeout: float) -> tuple[bool, int | None]:
    """Single HTTP GET to /health.  Never raises — errors → offline."""
    try:
        resp = _call("GET", server_url, _api_path("health"), "", "health",
                      timeout=timeout)
        online = resp.status_code == 200
        server_ts_str = resp.headers.get("Server-Time")
        server_ts = int(server_ts_str) if server_ts_str else None
        return online, server_ts
    except TransportError:
        return False, None
    except (ValueError, TypeError):
        return True, None  # server responded but header wasn't a valid int


def _write_health_cache(
    server_url: str, now: float, online: bool, server_ts: int | None,
) -> None:
    """Persist result to in-memory and file caches."""
    file_cache = _read_file_cache()
    _cache[server_url] = (now, online, server_ts)
    file_cache[server_url] = (now, online, server_ts)
    _prune_cache(file_cache)
    _write_file_cache(file_cache)


def is_online(server_url: str, timeout: float = 1.5) -> bool:
    """Return True if the remote server is reachable.

    All errors (timeout, DNS failure, connection refused, non-200) map to
    ``False``.  Results are cached across CLI invocations.
    """
    return _probe(server_url, timeout)[0]


def check_clock_skew(server_url: str, timeout: float = 1.5) -> int | None:
    """Return the clock skew in seconds (server_time - local_time), or None.

    Positive → local clock is behind the server.
    Negative → local clock is ahead.
    None → server unreachable or missing header.

    Uses the same cache as ``is_online`` — only one HTTP call is made.
    """
    online, server_ts = _probe(server_url, timeout)
    if not online or server_ts is None:
        return None
    return compute_clock_skew(server_ts, int(time.time()))


def _prune_cache(data: dict) -> None:
    """Keep only the N most recent entries to prevent unbounded growth."""
    if len(data) <= _MAX_CACHE_ENTRIES:
        return
    sorted_entries = sorted(data.items(), key=lambda kv: (kv[1][0], kv[0]), reverse=True)
    for key, _ in sorted_entries[_MAX_CACHE_ENTRIES:]:
        del data[key]
