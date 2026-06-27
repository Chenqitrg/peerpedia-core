# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Peer discovery — client-side logic for finding and tracking peers."""

from peerpedia_core.core.discover import (
    discover_articles,
    discover_followers,
    discover_following,
    discover_network,
    discover_notifications,
    discover_shares,
)
from peerpedia_core.social.discovery import (
    add_peer, get_known_peers, merge_peers, record_peer_result,
)
