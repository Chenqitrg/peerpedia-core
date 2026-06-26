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

import httpx

from peerpedia_core.config.paths import DATA_ROOT as _DATA_ROOT

logger = logging.getLogger(__name__)

# ── Connection result cache ──────────────────────────────────────────────
# Two-tier: in-memory (fast, same-process) + file (survives across CLI runs).
# Avoids repeated 1.5s timeouts when a dead server is checked by multiple
# commands in quick succession (e.g. sync status then following).

_CACHE_TTL = 30.0  # seconds

# In-memory cache — same process, zero disk I/O.
# Format: (timestamp, online, server_ts_or_none)
_cache: dict[str, tuple[float, bool, int | None]] = {}

# File cache — cross-process.  Stored as {url: [timestamp, online, server_ts]}.
_CACHE_FILE = _DATA_ROOT / "server_health.json"
_MAX_CACHE_ENTRIES = 10  # prevent unbounded growth

# Persistent httpx client — avoids creating a new connection per probe.
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Return a shared httpx.Client for health checks."""
    global _client
    if _client is None:
        _client = httpx.Client(timeout=httpx.Timeout(5.0))
    return _client


def _read_file_cache() -> dict[str, tuple[float, bool, int | None]]:
    """Read health cache from disk.  Returns {} on any error.

    Handles backward compat: old cache entries are ``[timestamp, bool]``
    (2 elements); current format is ``[timestamp, bool, server_ts]``.
    """
    try:
        raw = json.loads(_CACHE_FILE.read_text())
        result: dict[str, tuple[float, bool, int | None]] = {}
        for k, v in raw.items():
            ts = float(v[0])
            online = bool(v[1])
            server_ts = int(v[2]) if len(v) > 2 and v[2] is not None else None
            result[k] = (ts, online, server_ts)
        return result
    except (OSError, json.JSONDecodeError, ValueError, KeyError, IndexError):
        logger.debug("Health cache read error for %s", _CACHE_FILE, exc_info=True)
    return {}


def _write_file_cache(data: dict[str, tuple[float, bool, int | None]]) -> None:
    """Write health cache to disk atomically (best-effort, never raises)."""
    try:
        _DATA_ROOT.mkdir(parents=True, exist_ok=True)
        serializable = {k: [v[0], v[1], v[2]] for k, v in data.items()}
        tmp = _DATA_ROOT / ".server_health.tmp"
        tmp.write_text(json.dumps(serializable))
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
    """Single HTTP GET to ``/health``.  Returns ``(online, server_timestamp)``.

    Results are cached in memory AND on disk for 30 seconds (±1s jitter to
    prevent cache stampede from concurrent CLI processes).  Callers that
    only need one piece use the thin wrappers ``is_online`` and
    ``check_clock_skew``.
    """
    now = time.time()
    # Per-call jitter so concurrent processes don't all expire the cache
    # at exactly the same instant and stampede the server.
    ttl = _CACHE_TTL + random.uniform(-1.0, 1.0)

    # 1. In-memory cache (same process).
    if server_url in _cache:
        cached_time, cached_online, cached_ts = _cache[server_url]
        if now - cached_time < ttl:
            return cached_online, cached_ts

    # 2. File cache (cross-process).
    file_cache = _read_file_cache()
    if server_url in file_cache:
        cached_time, cached_online, cached_ts = file_cache[server_url]
        if now - cached_time < ttl:
            _cache[server_url] = (cached_time, cached_online, cached_ts)
            return cached_online, cached_ts

    # 3. Single HTTP probe (reuses persistent client for connection pooling).
    try:
        response = _get_client().get(f"{server_url}/health", timeout=timeout)
        online = response.status_code == 200
        server_ts_str = response.headers.get("Server-Time")
        server_ts = int(server_ts_str) if server_ts_str else None
    except httpx.HTTPError:
        online = False
        server_ts = None
    except (ValueError, TypeError):
        online = True
        server_ts = None  # header present but not an int

    # 4. Persist to both caches.
    entry = (now, online, server_ts)
    _cache[server_url] = entry
    file_cache[server_url] = entry
    _prune_cache(file_cache)
    _write_file_cache(file_cache)

    return online, server_ts


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
    return server_ts - int(time.time())


def _prune_cache(data: dict) -> None:
    """Keep only the N most recent entries to prevent unbounded growth."""
    if len(data) <= _MAX_CACHE_ENTRIES:
        return
    sorted_entries = sorted(data.items(), key=lambda kv: (kv[1][0], kv[0]), reverse=True)
    for key, _ in sorted_entries[_MAX_CACHE_ENTRIES:]:
        del data[key]
