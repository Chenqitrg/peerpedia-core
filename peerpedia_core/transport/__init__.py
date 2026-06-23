# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport facade — re-exports the active transport's functions.

When switching from HTTP to P2P, only this file changes.
"""

from peerpedia_core.transport.health import is_online
from peerpedia_core.transport.http_client import (
    ancestor_probe,
    fetch_articles,
    fetch_bookmarks,
    fetch_bundle,
    fetch_followers,
    fetch_following,
    fetch_head,
    post_article,
    push_bookmark,
    push_bundle,
    push_follow,
    push_unfollow,
)
