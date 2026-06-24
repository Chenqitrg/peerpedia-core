# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User routes — social graph (following / followers / articles).

Every handler calls ONE commands function and returns the result as JSON.
All routes require auth (Ed25519 signature via ``AuthMiddleware``)::

    GET  /api/v1/users/{id}/following  → _following    who this user follows
    GET  /api/v1/users/{id}/followers  → _followers    who follows this user
    GET  /api/v1/users/{id}/articles   → _articles     articles by this user
    POST /api/v1/users/{id}/follow     → _follow       follow a user
    POST /api/v1/users/{id}/unfollow   → _unfollow     unfollow a user
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from peerpedia_core.commands import (
    follow_user,
    get_follower_views,
    get_following_views,
    list_user_article_views,
    unfollow_user,
)
from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.transport.shared import _validate_id


# ── Handlers ─────────────────────────────────────────────────────────────


async def _following(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    return JSONResponse(get_following_views(request.state.db, user_id))


async def _followers(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    return JSONResponse(get_follower_views(request.state.db, user_id))


async def _follow(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    followed_id = payload.get("followed_id")
    if not followed_id:
        raise BadRequestError("Missing required field: 'followed_id'")
    follow_user(request.state.db, user_id, followed_id)
    return JSONResponse({"ok": True})


async def _unfollow(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    followed_id = payload.get("followed_id")
    if not followed_id:
        raise BadRequestError("Missing required field: 'followed_id'")
    unfollow_user(request.state.db, user_id, followed_id)
    return JSONResponse({"ok": True})


async def _articles(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    limit = min(int(request.query_params.get("limit", 20)), 100)
    offset = int(request.query_params.get("offset", 0))
    return JSONResponse(list_user_article_views(
        request.state.db, user_id, limit=limit, offset=offset,
    ))


# ── Route table ──────────────────────────────────────────────────────────


ROUTES = [
    Route("/api/v1/users/{user_id}/following", _following, methods=["GET"]),
    Route("/api/v1/users/{user_id}/followers", _followers, methods=["GET"]),
    Route("/api/v1/users/{user_id}/articles", _articles, methods=["GET"]),
    Route("/api/v1/users/{user_id}/follow", _follow, methods=["POST"]),
    Route("/api/v1/users/{user_id}/unfollow", _unfollow, methods=["POST"]),
]
