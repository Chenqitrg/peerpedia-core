# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Server CLI handler — ``peerpedia server start``."""

from __future__ import annotations


def _cmd_server_start(args):
    """Start the PeerPedia HTTP server (personal daemon).

    Binds 127.0.0.1:8080 by default — use ``--host 0.0.0.0`` to accept
    connections from other peers.  Single worker — SQLite requires it.
    """
    import uvicorn

    from peerpedia_core.transport.http_server import create_app

    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        workers=1,
    )
