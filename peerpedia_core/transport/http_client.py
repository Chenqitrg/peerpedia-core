# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport facade — re-exports all HTTP functions.

Every HTTP call in the entire project goes through this module.  If the
transport protocol changes (e.g. WebSocket, gRPC, Unix socket), only the
three backing modules need to be replaced.  No other module knows about HTTP.

Internal structure::

    _http_core.py      — shared client pool, helpers, signed get/post
    http_articles.py   — article sync, bundle protocol, search, metadata
    http_social.py     — social graph, discovery, key rotation, shares

All public functions raise ``TransportError`` on network failure and
``ProtocolError`` on unexpected server responses.
"""

# Infrastructure (shared client, close on shutdown)
from peerpedia_core.transport._http_core import close_client

# Article sync + bundle protocol
from peerpedia_core.transport.http_articles import (
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

# Social graph + discovery + key rotation + shares
from peerpedia_core.transport.http_social import (
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
