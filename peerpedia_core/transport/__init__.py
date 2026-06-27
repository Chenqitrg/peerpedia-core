# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport facade — ``Transport`` dataclass bundles all P2P callables.

``core/`` takes a ``Transport`` instance — symmetric orchestration for
``sync_article.py`` and ``sync_social.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


def close_client():
    """Close the shared HTTP client (call on shutdown)."""
    from peerpedia_core.transport.http._core import close_client as _close
    _close()


@dataclass
class Transport:
    """All P2P transport callables — single surface for bundle + discover.

    ``Transport.from_http()`` returns a default HTTP-wired instance.
    Swap the callbacks for gRPC / mock / in-memory transport.
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

    @classmethod
    def from_http(cls) -> Transport:
        """Wire HTTP callbacks (the default transport implementation)."""
        from peerpedia_core.transport.http.articles import (
            _ancestor_probe, _fetch_bundle, _fetch_head, _fetch_meta,
            _fetch_repo, _fetch_search, _fetch_source, _fetch_user_articles,
            _push_bundle, _push_repo,
        )
        from peerpedia_core.transport.http.social import (
            _fetch_followers, _fetch_following, _fetch_notifications,
            _fetch_peers, _fetch_school, _fetch_shares, _fetch_user,
            _push_follow, _push_key_rotation, _push_peer_registration,
            _push_share, _push_share_remove, _push_unfollow,
        )
        from peerpedia_core.transport.http.health import check_clock_skew, is_online

        return cls(
            ancestor_probe=_ancestor_probe,
            fetch_head=_fetch_head,
            push_bundle=_push_bundle,
            fetch_bundle=_fetch_bundle,
            fetch_repo=_fetch_repo,
            push_repo=_push_repo,
            fetch_source=_fetch_source,
            fetch_following=_fetch_following,
            fetch_followers=_fetch_followers,
            fetch_shares=_fetch_shares,
            fetch_notifications=_fetch_notifications,
            fetch_user_articles=_fetch_user_articles,
            fetch_search=_fetch_search,
            fetch_meta=_fetch_meta,
            fetch_peers=_fetch_peers,
            fetch_school=_fetch_school,
            fetch_user=_fetch_user,
            push_peer_registration=_push_peer_registration,
            push_follow=_push_follow,
            push_unfollow=_push_unfollow,
            push_key_rotation=_push_key_rotation,
            push_share=_push_share,
            push_share_remove=_push_share_remove,
            is_online=is_online,
            check_clock_skew=check_clock_skew,
        )
