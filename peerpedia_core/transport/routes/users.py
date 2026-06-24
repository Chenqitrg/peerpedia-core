# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User routes — social graph (following / followers / articles).

Every handler reads/writes the DB through ``social/server`` functions.
All routes require auth (Ed25519 signature via ``AuthMiddleware``)::

    GET  /api/v1/users/{id}/following  → _following    who this user follows
    GET  /api/v1/users/{id}/followers  → _followers    who follows this user
    GET  /api/v1/users/{id}/articles   → _articles     articles by this user
    POST /api/v1/users/{id}/follow     → _follow       follow a user
    POST /api/v1/users/{id}/unfollow   → _unfollow     unfollow a user

Bookmark routes were removed — bookmarks are local-only, not shared.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from peerpedia_core.commands import get_author_ids
from peerpedia_core.exceptions import BadRequestError  # for _follow/_unfollow
from peerpedia_core.social.server import (
    get_articles as social_get_articles,
    get_followers as social_get_followers,
    get_following as social_get_following,
    handle_follow as social_handle_follow,
    handle_unfollow as social_handle_unfollow,
)
from peerpedia_core.transport.shared import _validate_id


# ── Handlers ─────────────────────────────────────────────────────────────


async def _following(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    db = request.state.db
    users = social_get_following(db, user_id)
    return JSONResponse([u.to_dict() for u in users])


async def _followers(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    db = request.state.db
    users = social_get_followers(db, user_id)
    return JSONResponse([u.to_dict() for u in users])


async def _follow(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    followed_id = payload.get("followed_id")
    if not followed_id:
        raise BadRequestError("Missing required field: 'followed_id'")
    db = request.state.db
    social_handle_follow(db, user_id, followed_id)
    return JSONResponse({"ok": True})


async def _unfollow(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    followed_id = payload.get("followed_id")
    if not followed_id:
        raise BadRequestError("Missing required field: 'followed_id'")
    db = request.state.db
    social_handle_unfollow(db, user_id, followed_id)
    return JSONResponse({"ok": True})


async def _articles(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    limit = min(int(request.query_params.get("limit", 20)), 100)
    offset = int(request.query_params.get("offset", 0))
    db = request.state.db
    articles = social_get_articles(db, user_id, limit=limit, offset=offset)
    return JSONResponse([
        {**a.to_dict(), "authors": get_author_ids(db, a.id)}
        for a in articles
    ])


# ── Route table ──────────────────────────────────────────────────────────


ROUTES = [
    Route("/api/v1/users/{user_id}/following", _following, methods=["GET"]),
    Route("/api/v1/users/{user_id}/followers", _followers, methods=["GET"]),
    Route("/api/v1/users/{user_id}/articles", _articles, methods=["GET"]),
    Route("/api/v1/users/{user_id}/follow", _follow, methods=["POST"]),
    Route("/api/v1/users/{user_id}/unfollow", _unfollow, methods=["POST"]),
]
