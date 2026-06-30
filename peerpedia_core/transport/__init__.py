# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport protocol — ``Transport`` dataclass bundles all P2P callables.

``core/`` takes a ``Transport`` instance — symmetric orchestration for
``sync_article.py`` and ``sync_social.py``.  The HTTP factory lives in
``transport/http/factory.py`` to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Transport:
    """All P2P transport callables — single surface for bundle + discover.

    Use ``from_http()`` in ``transport/http/factory.py`` for the
    default HTTP implementation.  Swap the callbacks for gRPC / mock.
    """
    # ── Article / bundle ──────────────────────────────────────────────────
    ancestor_probe: Callable[[str, str, str], bool | None]
    fetch_head: Callable[[str, str], str | None]
    push_bundle: Callable[[str, str, bytes], None]
    fetch_bundle: Callable[[str, str, str | None], bytes | None]
    fetch_repo: Callable[[str, str], str | None]
    push_repo: Callable[[str, str, str], bool]
    fetch_source: Callable[[str, str], tuple[str, str] | None]

    # ── Social / discover ─────────────────────────────────────────────────
    fetch_following: Callable[..., list[dict] | None]
    fetch_followers: Callable[..., list[dict] | None]
    fetch_shares: Callable[..., list[dict] | None]
    fetch_notifications: Callable[..., list[dict] | None]
    fetch_user_articles: Callable[..., list[dict] | None]

    # ── Search / metadata ─────────────────────────────────────────────────
    fetch_search: Callable[..., list[dict] | None]
    fetch_meta: Callable[[str, str], dict | None]

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
