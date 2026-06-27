# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport facade — re-exports the active transport's functions.

When switching from HTTP to P2P, only this file changes.
"""

from peerpedia_core.transport.guards import fetch_with_auth_fallback, require_fetch_response
from peerpedia_core.transport.http._core import close_client
from peerpedia_core.transport.http.articles import (
    ancestor_probe,
    fetch_article_meta,
    fetch_article_repo,
    fetch_article_source,
    fetch_head,
    fetch_incremental_bundle,
    fetch_search,
    fetch_user_articles,
    push_article_repo,
    push_bundle,
)
from peerpedia_core.transport.http.health import check_clock_skew, is_online
from peerpedia_core.transport.http.social import (
    fetch_followers,
    fetch_following,
    fetch_notifications,
    fetch_peers,
    fetch_school,
    fetch_shares,
    fetch_user,
    push_follow,
    push_key_rotation,
    push_peer_registration,
    push_share,
    push_share_remove,
    push_unfollow,
)
