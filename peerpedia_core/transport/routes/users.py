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

from peerpedia_core.crypto import load_public_key
from peerpedia_core.commands import (
    add_share,
    follow_user,
    get_follower_views,
    get_following_views,
    get_shares_for_user,
    get_top_users_by_followers,
    list_user_article_views,
    remove_share,
    unfollow_user,
    update_user_public_key,
)
from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.policies.articles import PUBLIC_READABLE_STATUSES
from peerpedia_core.transport.shared import _ok_response, _parse_pagination, _require_field, _validate_id


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
    followed_id = _require_field(payload, "followed_id")
    follow_user(request.state.db, user_id, followed_id)
    return _ok_response()


async def _unfollow(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    followed_id = _require_field(payload, "followed_id")
    unfollow_user(request.state.db, user_id, followed_id)
    return _ok_response()


async def _rotate_key(request: Request) -> JSONResponse:
    """POST /api/v1/users/{user_id}/rotate-key — update stored public key.

    AuthMiddleware verifies the request is signed by *user_id* with the
    current private key.  The new public key is stored immediately.
    """
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    new_pubkey = _require_field(payload, "public_key")
    if not isinstance(new_pubkey, str) or len(new_pubkey) != 64:
        raise BadRequestError(
            "public_key must be a 64-character hex string"
        )
    try:
        key_bytes = bytes.fromhex(new_pubkey)
    except ValueError:
        raise BadRequestError(
            "public_key must be a valid hex string"
        )
    # Validate the Ed25519 curve point — reject low-order points and
    # points-off-curve that would break all future auth for this user.
    try:
        load_public_key(key_bytes)
    except Exception as e:
        raise BadRequestError(
            f"public_key is not a valid Ed25519 key: {e}"
        )
    update_user_public_key(request.state.db, user_id, new_pubkey)
    return _ok_response()


async def _articles(request: Request) -> JSONResponse:
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    limit, offset = _parse_pagination(request)
    # Policy: unauthenticated peers see only public-readable statuses.
    # The author sees all their own articles.
    requester = getattr(request.state, "user_id", None)
    status = None if requester == user_id else PUBLIC_READABLE_STATUSES
    return JSONResponse(list_user_article_views(
        request.state.db, user_id, status=status, limit=limit, offset=offset,
    ))


async def _push_share(request: Request) -> JSONResponse:
    """POST/DELETE /api/v1/users/{user_id}/share — record or remove a share."""
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    payload = await request.json()
    article_id = _require_field(payload, "article_id")

    if request.method == "DELETE":
        remove_share(request.state.db, user_id, article_id)
        return _ok_response()

    result = add_share(
        request.state.db, user_id, article_id,
        recipient_id=payload.get("recipient_id"),
        comment=payload.get("comment"),
    )
    return JSONResponse(result)


async def _get_shares(request: Request) -> JSONResponse:
    """GET /api/v1/users/{user_id}/shares — list shares by a user."""
    user_id = request.path_params["user_id"]
    _validate_id(user_id, "user_id")
    return JSONResponse(get_shares_for_user(request.state.db, user_id))


async def _school(request: Request) -> JSONResponse:
    """GET /api/v1/school — top users by follower count (public, no auth)."""
    limit, _ = _parse_pagination(request)
    return JSONResponse(get_top_users_by_followers(request.state.db, limit=limit))


# ── Route table ──────────────────────────────────────────────────────────


ROUTES = [
    Route("/api/v1/school", _school, methods=["GET"]),
    Route("/api/v1/users/{user_id}/following", _following, methods=["GET"]),
    Route("/api/v1/users/{user_id}/followers", _followers, methods=["GET"]),
    Route("/api/v1/users/{user_id}/articles", _articles, methods=["GET"]),
    Route("/api/v1/users/{user_id}/follow", _follow, methods=["POST"]),
    Route("/api/v1/users/{user_id}/unfollow", _unfollow, methods=["POST"]),
    Route("/api/v1/users/{user_id}/rotate-key", _rotate_key, methods=["POST"]),
    Route("/api/v1/users/{user_id}/share", _push_share, methods=["POST", "DELETE"]),
    Route("/api/v1/users/{user_id}/shares", _get_shares, methods=["GET"]),
]
