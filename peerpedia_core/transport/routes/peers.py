# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""P2P peer discovery — GET /api/v1/peers endpoint.

Returns known peer URLs so clients can discover the network without
out-of-band configuration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from peerpedia_core.config.params import params

_PEERS_FILE = Path.home() / ".peerpedia" / "peers.json"


def _load_peers() -> list[str]:
    """Load known peers from disk, falling back to seed list."""
    if _PEERS_FILE.is_file():
        try:
            with open(_PEERS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return list(params.discovery.seed_peers)


def _save_peers(peers: list[str]) -> None:
    """Persist known peers to disk."""
    _PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_PEERS_FILE, "w") as f:
        json.dump(peers[: params.discovery.max_known_peers], f)


def add_peer(url: str) -> None:
    """Register a new peer URL (idempotent)."""
    peers = _load_peers()
    if url not in peers:
        peers.insert(0, url)
        _save_peers(peers)


async def _peers_endpoint(request: Request) -> JSONResponse:
    """GET /api/v1/peers → known peer URLs."""
    return JSONResponse({"peers": _load_peers()})


ROUTES = [
    Route("/api/v1/peers", _peers_endpoint, methods=["GET"]),
]
