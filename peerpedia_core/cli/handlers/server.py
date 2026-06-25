# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Server CLI handler — ``peerpedia server start``."""

from __future__ import annotations

import logging
import threading
import time

from peerpedia_core.config.params import params
from peerpedia_core.social.discovery import merge_peers, get_known_peers
from peerpedia_core.transport import push_peer_registration

_logger = logging.getLogger(__name__)


def _cmd_server_start(args):
    """Start the PeerPedia HTTP server (personal daemon).

    Binds 127.0.0.1:8080 by default — use ``--host 0.0.0.0`` to accept
    connections from other peers.  Single worker — SQLite requires it.
    """
    import uvicorn

    from peerpedia_core.transport.http_server import create_app

    # Background peer discovery: merge seed peers and announce this server.
    public_url = getattr(args, "public_url", None) or None
    if public_url:
        _start_discovery_thread(public_url)

    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        workers=1,
    )


def _start_discovery_thread(public_url: str) -> None:
    """Spawn a daemon thread that discovers and announces peers.

    Reads seed peers from ``params.discovery.seed_peers``, fetches their
    known peer lists, and announces *public_url* to each discovered peer.
    Only touches ``peers.json`` — no DB access.
    """

    def _discover():
        # Wait for uvicorn to start before making outbound connections.
        time.sleep(2)

        # Step 1: merge seed peers.
        for seed in params.discovery.seed_peers:
            try:
                n = merge_peers(seed)
                if n:
                    _logger.info("Discovered %d peer(s) from seed %s", n, seed)
            except Exception as e:
                _logger.debug("Seed peer %s unreachable: %s", seed, e)

        # Step 2: announce this server to all known peers.
        peers = get_known_peers()
        for peer in peers:
            try:
                push_peer_registration(peer, public_url)
                _logger.debug("Registered with peer %s", peer)
            except Exception as e:
                _logger.debug("Peer registration to %s failed: %s", peer, e)

    t = threading.Thread(target=_discover, daemon=True)
    t.start()
