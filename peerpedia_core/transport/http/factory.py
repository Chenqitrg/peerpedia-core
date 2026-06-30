# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport factory — wires ``Transport`` with HTTP callbacks.

Lives in ``transport/http/`` so ``transport/__init__.py`` stays pure
(``Transport`` dataclass only), breaking the circular import between
Transport and its HTTP implementation.
"""

from __future__ import annotations

from peerpedia_core.transport import Transport
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


def from_http() -> Transport:
    """Return a ``Transport`` wired with HTTP callbacks."""
    return Transport(
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
