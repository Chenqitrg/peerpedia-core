# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social graph exchange — peer-to-peer social data propagation.

Client-side (exchange.py): fetch social graph from a peer, merge into local DB.
Server-side (server.py): serve social data to peers (called by HTTP routes).
"""

from peerpedia_core.social.exchange import (
    discover_articles,
    discover_followers,
    discover_following,
    discover_notifications,
    discover_shares,
)

__all__ = [
    "discover_following",
    "discover_followers",
    "discover_articles",
    "discover_notifications",
    "discover_shares",
]
