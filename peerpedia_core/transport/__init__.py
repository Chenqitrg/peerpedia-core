# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport facade — ``Transport`` dataclass bundles all P2P callables.

Architecture::

    server/http/  ← HTTP callbacks (paths, status codes, httpx)
    cli/          ← wires HTTP callbacks into Transport instance
    Transport     ← pure dataclass, no imports from server/http/
    core/         ← takes Transport instance

``core/bundle.py`` and ``core/discover.py`` both take a ``Transport``
instance — symmetric orchestration over a single transport surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

def close_client():
    """Close the shared HTTP client (call on shutdown)."""
    from peerpedia_core.server.http._core import close_client as _close
    _close()


@dataclass
class Transport:
    """All P2P transport callables — single surface for bundle + discover.

    Constructed at the CLI/REPL layer by wiring ``server/http/`` callbacks.
    ``core/`` imports ``Transport``, not the individual functions.
    """
    # ── Article / bundle ──────────────────────────────────────────────────
    ancestor_probe: Callable[[str, str, str], bool | None]
    fetch_head: Callable[[str, str], str | None]
    push_bundle: Callable[[str, str, bytes], None]
    fetch_incremental_bundle: Callable[[str, str, str | None], bytes | None]
    fetch_article_repo: Callable[[str, str], str | None]
    push_article_repo: Callable[[str, str, str], bool]
    fetch_article_source: Callable[[str, str], tuple[str, str] | None]

    # ── Social / discover ─────────────────────────────────────────────────
    fetch_following: Callable[..., list[dict] | None]
    fetch_followers: Callable[..., list[dict] | None]
    fetch_shares: Callable[..., list[dict] | None]
    fetch_notifications: Callable[..., list[dict] | None]
    fetch_user_articles: Callable[..., list[dict] | None]

    # ── Search / metadata ─────────────────────────────────────────────────
    fetch_search: Callable[..., list[dict] | None]
    fetch_article_meta: Callable[[str, str], dict | None]

    # ── Peers / school / users ────────────────────────────────────────────
    fetch_peers: Callable[[str], list[str]]
    fetch_school: Callable[[str, int], list[dict]]
    fetch_user: Callable[[str, str], dict | None]
    push_peer_registration: Callable[[str, str], bool]

    # ── Social push ───────────────────────────────────────────────────────
    push_follow: Callable[..., bool]
    push_unfollow: Callable[..., bool]
    push_key_rotation: Callable[..., bool]
    push_share: Callable[..., bool]
    push_share_remove: Callable[..., bool]

    # ── Connectivity ──────────────────────────────────────────────────────
    is_online: Callable[[str], bool]
    check_clock_skew: Callable[[str], int | None]
