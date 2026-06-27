# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""P2P peer discovery — client-side logic for finding and tracking peers.

This module is the single source of truth for ``~/.peerpedia/peers.json``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from peerpedia_core.config.params import params
from peerpedia_core.config.paths import DATA_ROOT

if TYPE_CHECKING:
    from peerpedia_core.transport import Transport

_PEERS_FILE = DATA_ROOT / "peers.json"

# ── Backoff state ────────────────────────────────────────────────────────────

# In-memory cache of per-peer failure state: {url: {"fail_count": N, "last_failed_at": ts}}.
# Persisted to peers.json alongside the URL list.
_backoff: dict[str, dict] = {}
_backoff_hydrated = False


def _ensure_backoff_hydrated() -> None:
    """Lazily hydrate backoff state from peers.json on first access."""
    global _backoff_hydrated
    if not _backoff_hydrated:
        _hydrate_backoff()
        _backoff_hydrated = True


def _load_peers_raw() -> list:
    """Load the raw peer list from disk (list of urls or list of dicts)."""
    if _PEERS_FILE.is_file():
        try:
            with open(_PEERS_FILE) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return list(params.discovery.seed_peers)


def _save_peers_raw(peers: list) -> None:
    """Persist peers to disk, capped at max_known_peers."""
    _PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_PEERS_FILE, "w") as f:
        json.dump(peers[: params.discovery.max_known_peers], f)


def _is_peer_backoff(url: str) -> bool:
    """Return True if *url* is in exponential backoff and should be skipped."""
    _ensure_backoff_hydrated()
    if url not in _backoff:
        return False
    state = _backoff[url]
    fail_count = state.get("fail_count", 0)
    if fail_count == 0:
        return False
    # Exponential backoff: 1m, 2m, 4m, 8m, 16m (max 5 failures)
    delay = min(60 * (2 ** (fail_count - 1)), 960)
    elapsed = time.time() - state.get("last_failed_at", 0)
    return elapsed < delay


def _peer_failed(url: str) -> None:
    """Record a failure for *url*, incrementing backoff."""
    _ensure_backoff_hydrated()
    now = time.time()
    if url not in _backoff:
        _backoff[url] = {"fail_count": 1, "last_failed_at": now}
    else:
        _backoff[url]["fail_count"] = min(_backoff[url].get("fail_count", 0) + 1, 5)
        _backoff[url]["last_failed_at"] = now
    # Persist backoff state
    _persist_backoff()


def _peer_succeeded(url: str) -> None:
    """Reset backoff for *url* after a successful connection."""
    _ensure_backoff_hydrated()
    if url in _backoff:
        del _backoff[url]
        _persist_backoff()


def _persist_backoff() -> None:
    """Write backoff state into peers.json alongside URLs."""
    entries = []
    for url in get_known_peers():
        entry: dict = {"url": url}
        if url in _backoff:
            entry["fail_count"] = _backoff[url].get("fail_count", 0)
            entry["last_failed_at"] = _backoff[url].get("last_failed_at", 0)
        entries.append(entry)
    _save_peers_raw(entries)


def _hydrate_backoff() -> None:
    """Load backoff state from peers.json on module init."""
    if not _PEERS_FILE.is_file():
        return
    try:
        with open(_PEERS_FILE) as f:
            data = json.load(f)
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "fail_count" in entry:
                        _backoff[entry["url"]] = {
                            "fail_count": entry.get("fail_count", 0),
                            "last_failed_at": entry.get("last_failed_at", 0),
                        }
    except (json.JSONDecodeError, OSError):
        pass


# ── Public API ───────────────────────────────────────────────────────────────


def get_known_peers(*, skip_backoff: bool = True) -> list[str]:
    """Return known peer URLs: discovered + seed list.

    When *skip_backoff* is True (default), peers in exponential backoff
    are excluded from the returned list.
    """
    raw = _load_peers_raw()
    urls: list[str] = []
    for item in raw:
        url = item["url"] if isinstance(item, dict) else item
        if url not in urls:
            urls.append(url)

    if skip_backoff:
        urls = [u for u in urls if not _is_peer_backoff(u)]

    # Merge with seed peers (always at the end, never skipped by backoff)
    for sp in params.discovery.seed_peers:
        if sp not in urls:
            urls.append(sp)

    return urls


def add_peer(url: str) -> None:
    """Register a new peer URL (idempotent). Inserts at front of list."""
    raw = _load_peers_raw()
    # Extract existing URLs
    existing = {item["url"] if isinstance(item, dict) else item for item in raw}
    if url not in existing:
        raw.insert(0, {"url": url})
        _save_peers_raw(raw)


def merge_peers(transport: Transport, server_url: str) -> int:
    """Fetch peers via *transport* and merge into the local peer list.

    Returns count of new peers discovered.
    """
    try:
        remote = transport.fetch_peers(server_url)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to fetch peers from %s", server_url, exc_info=True
        )
        return 0

    local_urls = set(get_known_peers(skip_backoff=False))
    new_count = 0
    for url in remote:
        if url not in local_urls:
            add_peer(url)
            local_urls.add(url)
            new_count += 1

    return new_count


def record_peer_result(url: str, success: bool) -> None:
    """Record success/failure for *url* to update backoff state."""
    if success:
        _peer_succeeded(url)
    else:
        _peer_failed(url)


# Backoff state is now hydrated lazily on first access via
# ``_ensure_backoff_hydrated()`` — no module-level I/O side effect.
