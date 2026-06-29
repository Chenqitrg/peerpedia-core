# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Server CLI handler — ``peerpedia server start``."""

from __future__ import annotations

import logging
import threading
import time

from peerpedia_core.cli.bundle_utils import _TRANSPORT
from peerpedia_core.cli.info import _log

_logger = logging.getLogger(__name__)


def _cmd_server_start(args):
    """Start the PeerPedia HTTP server (personal daemon).

    Binds 127.0.0.1:8080 by default — use ``--host 0.0.0.0`` to accept
    connections from other peers.  Single worker — SQLite requires it.
    """
    import uvicorn

    from peerpedia_core.server.app import create_app

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
    """Spawn a daemon thread that announces this server to the peer network."""

    def _run():
        # Wait for uvicorn to start before making outbound connections.
        time.sleep(2)
        from peerpedia_core.app.commands.sync import announce_to_peers
        seeds, peers = announce_to_peers(_TRANSPORT, public_url)
        if seeds or peers:
            _log("L_DISCOVERED_PEERS", level="info",
                 seeds=seeds, peers=peers, url=public_url)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
