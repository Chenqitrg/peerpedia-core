# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Peer endpoints — list and register known peers.

GET  /api/v1/peers → known peer URLs
POST /api/v1/peers → register a new peer URL
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from peerpedia_core.core import add_peer, get_known_peers


async def _peers_endpoint(request: Request) -> JSONResponse:
    """GET /api/v1/peers → known peer URLs."""
    return JSONResponse({"peers": get_known_peers()})


async def _register_peer(request: Request) -> JSONResponse:
    """POST /api/v1/peers — register a new peer URL (idempotent)."""
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "url is required"}, status_code=400)
    add_peer(url)
    return JSONResponse({"status": "registered"})


ROUTES = [
    Route("/api/v1/peers", _peers_endpoint, methods=["GET"]),
    Route("/api/v1/peers", _register_peer, methods=["POST"]),
]
