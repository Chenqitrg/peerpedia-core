# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport facade — re-exports the active transport's functions.

When switching from HTTP to P2P, only this file changes.
"""

from peerpedia_core.transport.guards import require_fetch_response
from peerpedia_core.transport.health import is_online
from peerpedia_core.transport.http_client import (
    ancestor_probe,
    fetch_article_meta,
    fetch_article_repo,
    fetch_article_source,
    fetch_user_articles,
    fetch_incremental_bundle,
    fetch_followers,
    fetch_following,
    fetch_head,
    fetch_notifications,
    fetch_peers,
    push_peer_registration,
    fetch_school,
    fetch_search,
    fetch_shares,
    fetch_user,
    push_article_repo,
    push_bundle,
    push_follow,
    push_key_rotation,
    push_share,
    push_share_remove,
    push_unfollow,
)
