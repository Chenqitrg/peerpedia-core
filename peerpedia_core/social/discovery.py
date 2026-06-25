# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""P2P peer discovery — client-side logic for finding and tracking peers.

Uses the transport facade so switching from HTTP to P2P only requires
changing ``transport/__init__.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from peerpedia_core.config.params import params
from peerpedia_core.transport import fetch_peers

_PEERS_FILE = Path.home() / ".peerpedia" / "peers.json"


def get_known_peers() -> list[str]:
    """Return known peer URLs: user-configured + seed list + discovered."""
    peers: list[str] = []
    if _PEERS_FILE.is_file():
        try:
            peers = json.loads(_PEERS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Merge with seed peers (seed peers always at the end)
    for sp in params.discovery.seed_peers:
        if sp not in peers:
            peers.append(sp)

    return peers


def merge_peers(server_url: str) -> int:
    """Fetch peers from *server_url* and merge into local list.

    Returns count of new peers discovered.
    """
    try:
        remote = fetch_peers(server_url)
    except Exception:
        return 0

    local = get_known_peers()
    new_count = 0
    for url in remote:
        if url not in local:
            local.insert(0, url)
            new_count += 1

    if new_count:
        _PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PEERS_FILE.write_text(json.dumps(
            local[: params.discovery.max_known_peers],
        ))

    return new_count
