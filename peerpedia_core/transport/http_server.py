# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""ASGI app factory for the PeerPedia HTTP server.

Pure routing layer — no business logic.  Delegates to ``bundle/server``
and ``social/server`` for all handler logic.  This file only parses
HTTP requests, calls handlers, and returns HTTP responses.

Error handling: every ``PeerpediaError`` subclass maps to a specific HTTP
status code.  Unhandled exceptions → 500 with traceback in debug mode.

TODO(auth): zero authentication on all endpoints — anyone can push bundles,
follow users, or read social graphs for any user_id.  Add request signing
or bearer tokens so the server can verify the caller's identity.
TODO(infra): no request body size limit on POST /sync — a multi-GB bundle
body is read entirely into memory.  Add Content-Length check or streaming
limit before ``await request.body()``.
TODO(infra): no rate limiting — any endpoint can be hammered.
TODO(infra): DB session middleware uses URL prefix/suffix matching to decide
which routes need a session.  Fragile — a new route that needs DB but
doesn't match the pattern silently gets no session.  Use route-level
middleware or explicit dependency declaration.
TODO(infra): 500 errors include traceback in response body — information leak
in production.  Gate behind a debug flag or strip in non-debug mode.
TODO(content): no article content API — peers must sync the full git bundle
just to read an article.  Add GET /api/v1/articles/{id}?format=html that
returns compiled output so a reader doesn't need to sync first.
TODO(search): no article or user search endpoint — discovery is purely
social-graph-based.  Add GET /api/v1/search?q=... and /api/v1/users?q=...
so peers can find content without knowing exact IDs.
TODO(discovery): no bootstrap peer or server directory — new users must
know a server URL out-of-band.  Add a seed peer list or peer exchange
endpoint so the network is discoverable.
TODO(security): path traversal — ``article_id`` and ``user_id`` from URL
params are used directly in filesystem paths.  Validate that both are
UUIDs or safe identifiers before passing to ``ARTICLES_DIR / id``.
TODO(infra): no logging — zero ``print``, ``logging``, or structured log
output.  Errors, requests, and potential attacks are invisible.
TODO(infra): ``limit`` query param has no upper bound — ``limit=99999999``
fetches the entire database in one request.
TODO(correctness): ``ValueError`` and ``TypeError`` map to HTTP 400 — an
internal bug that raises ValueError is reported as a client error,
masking the real problem.  At minimum, log the traceback.
TODO(privacy): ``u.to_dict()`` in social handlers may expose sensitive
fields (public_key, email).  Audit the User.to_dict() output and
strip fields that should not leave the server.
"""

from __future__ import annotations

import traceback

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

import git as gitmod

from peerpedia_core.commands import get_author_ids
from peerpedia_core.config.paths import ARTICLES_DIR, DB_URL
from peerpedia_core.storage.db import db_session
from peerpedia_core.exceptions import (
    BadRequestError,
    ConflictError,
    NotAuthorizedError,
    NotFoundError,
    PeerpediaError,
    ProtocolError,
    SignatureVerificationError,
    TransportError,
)
from peerpedia_core.bundle.server import (
    apply_sync,
    check_ancestor,
    ingest_article,
    get_bundle,
    get_head,
)
from peerpedia_core.social.server import (
    get_articles as social_get_articles,
    get_bookmarks as social_get_bookmarks,
    get_followers as social_get_followers,
    get_following as social_get_following,
    handle_bookmark as social_handle_bookmark,
    handle_follow as social_handle_follow,
    handle_unfollow as social_handle_unfollow,
)

# ═══════════════════════════════════════════════════════════════════════════════
# DB session middleware
# ═══════════════════════════════════════════════════════════════════════════════


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Create a DB session per request for routes that need it.

    Skips session creation for routes that only touch git or are static:
    ``/health``, article head/bundle/ancestor, and first-time article push.
    """

    # Paths that need a DB session.
    _DB_ROUTES = frozenset({"/api/v1/users"})   # anything under /users/ needs DB
    _DB_SUFFIXES = ("/sync",)                   # POST /articles/{id}/sync needs DB

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        needs_db = (
            path.startswith(tuple(self._DB_ROUTES))
            or path.endswith(self._DB_SUFFIXES)
        )
        if not needs_db:
            return await call_next(request)

        with db_session(DB_URL) as db:
            request.state.db = db
            response = await call_next(request)
            return response


# ═══════════════════════════════════════════════════════════════════════════════
# Route handlers — thin wrappers around bundle_server / social_server
# ═══════════════════════════════════════════════════════════════════════════════


def _health(request: Request) -> JSONResponse:
    """GET /health → 200 ``{"status": "ok"}``.  No database access.

    TODO(infra): this is a fake health check — always returns 200 even if
    the database or filesystem is broken.  Add a real dependency check
    (e.g. verify articles directory exists, DB is reachable).
    """
    return JSONResponse({"status": "ok"})


async def _head(request: Request) -> JSONResponse:
    """GET /api/v1/articles/{article_id}/head → 200 + HEAD hash, or 404.

    Delegates to ``bundle_server.get_head``.
    """
    article_id = request.path_params["article_id"]
    result = get_head(ARTICLES_DIR / article_id)
    if result is None:
        raise NotFoundError(f"Article '{article_id}' not found")
    return JSONResponse({"hash": result})


async def _bundle(request: Request) -> Response:
    """GET /api/v1/articles/{article_id}/bundle?since= → bundle bytes, or 404.

    Delegates to ``bundle_server.get_bundle``.
    """
    article_id = request.path_params["article_id"]
    since_hash = request.query_params.get("since")
    result = get_bundle(ARTICLES_DIR / article_id, since_hash)
    if result is None:
        raise NotFoundError(f"Bundle not available for '{article_id}'")
    return Response(content=result, media_type="application/octet-stream")


async def _sync(request: Request) -> JSONResponse:
    """POST /api/v1/articles/{article_id}/sync → 200 with new HEAD, or 409.

    Reads the raw bundle body, then delegates to ``bundle_server.apply_sync``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    article_id = request.path_params["article_id"]
    bundle_bytes = await request.body()
    db = request.state.db
    new_head = apply_sync(db, article_id, bundle_bytes)
    return JSONResponse({"head": new_head})


async def _ancestor(request: Request) -> JSONResponse:
    """GET /api/v1/articles/{article_id}/ancestor/{hash} → 200 with boolean.

    Delegates to ``bundle_server.check_ancestor``.
    """
    article_id = request.path_params["article_id"]
    h = request.path_params["hash"]
    result = check_ancestor(ARTICLES_DIR / article_id, h)
    return JSONResponse({"ancestor": result})


async def _push_article_repo_handler(request: Request) -> JSONResponse:
    """POST /api/v1/articles → 201 with new HEAD, or 400 on missing fields.

    Validates ``id`` and ``repo_bundle`` before delegating to
    ``bundle_server.ingest_article``.
    """
    payload = await request.json()
    article_id = payload.get("id")
    if not article_id:
        raise BadRequestError("Missing required field: 'id'")
    if "repo_bundle" not in payload:
        raise BadRequestError("Missing required field: 'repo_bundle'")
    if not payload["repo_bundle"]:
        raise BadRequestError("Field 'repo_bundle' must not be empty")
    new_head = ingest_article(ARTICLES_DIR / article_id, payload)
    return JSONResponse({"head": new_head}, status_code=201)


async def _following(request: Request) -> JSONResponse:
    """GET /api/v1/users/{user_id}/following → 200 with list of user dicts.

    Delegates to ``social_server.get_following``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    db = request.state.db
    users = social_get_following(db, user_id)
    return JSONResponse([
        u.to_dict() for u in users
    ])


async def _followers(request: Request) -> JSONResponse:
    """GET /api/v1/users/{user_id}/followers → 200 with list of user dicts.

    Delegates to ``social_server.get_followers``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    db = request.state.db
    users = social_get_followers(db, user_id)
    return JSONResponse([
        u.to_dict() for u in users
    ])


async def _bookmarks(request: Request) -> JSONResponse:
    """GET /api/v1/users/{user_id}/bookmarks → 200 with list of article dicts.

    Delegates to ``social_server.get_bookmarks``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    db = request.state.db
    bookmarks = social_get_bookmarks(db, user_id)
    return JSONResponse([
        {"article_id": b.article_id, "bookmarked_at": str(b.created_at)}
        for b in bookmarks
    ])


async def _follow(request: Request) -> JSONResponse:
    """POST /api/v1/users/{user_id}/follow → 200 on success.

    Body: ``{"followed_id": "<uuid>"}``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    payload = await request.json()
    followed_id = payload.get("followed_id")
    if not followed_id:
        raise BadRequestError("Missing required field: 'followed_id'")
    db = request.state.db
    social_handle_follow(db, user_id, followed_id)
    return JSONResponse({"ok": True})


async def _unfollow(request: Request) -> JSONResponse:
    """POST /api/v1/users/{user_id}/unfollow → 200 on success.

    Body: ``{"followed_id": "<uuid>"}``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    payload = await request.json()
    followed_id = payload.get("followed_id")
    if not followed_id:
        raise BadRequestError("Missing required field: 'followed_id'")
    db = request.state.db
    social_handle_unfollow(db, user_id, followed_id)
    return JSONResponse({"ok": True})


async def _bookmark(request: Request) -> JSONResponse:
    """POST /api/v1/users/{user_id}/bookmark → 200 on success.

    Body: ``{"article_id": "<uuid>"}``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    payload = await request.json()
    article_id = payload.get("article_id")
    if not article_id:
        raise BadRequestError("Missing required field: 'article_id'")
    db = request.state.db
    social_handle_bookmark(db, user_id, article_id)
    return JSONResponse({"ok": True})


async def _articles(request: Request) -> JSONResponse:
    """GET /api/v1/users/{user_id}/articles?limit=&offset= → 200 with article dicts.

    Delegates to ``social_server.get_articles``.
    Requires a DB session (set by ``DBSessionMiddleware``).
    """
    user_id = request.path_params["user_id"]
    limit = int(request.query_params.get("limit", 20))
    offset = int(request.query_params.get("offset", 0))
    db = request.state.db
    articles = social_get_articles(db, user_id, limit=limit, offset=offset)
    return JSONResponse([
        {**a.to_dict(), "authors": get_author_ids(db, a.id)}
        for a in articles
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Error handlers
# ═══════════════════════════════════════════════════════════════════════════════

_ERROR_MAP: dict[type[Exception], int] = {
    NotFoundError: 404,
    NotAuthorizedError: 403,
    ConflictError: 409,
    BadRequestError: 400,
    SignatureVerificationError: 422,
    TransportError: 502,
    ProtocolError: 502,
    ValueError: 400,
    TypeError: 400,
    FileNotFoundError: 404,
}

_ERROR_MAP[gitmod.GitCommandError] = 500


async def _error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a raised exception to an HTTP status code and JSON error body.

    Walks ``_ERROR_MAP`` to find the matching exception type.  Unmapped
    exceptions default to 500 with a traceback in the response body.
    """
    status_code = 500
    for exc_type, code in _ERROR_MAP.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    body: dict = {"error": str(exc), "status": status_code}
    if status_code == 500:
        body["traceback"] = traceback.format_exc()

    return JSONResponse(body, status_code=status_code)


# ═══════════════════════════════════════════════════════════════════════════════
# App factory
# ═══════════════════════════════════════════════════════════════════════════════

_ROUTES = [
    Route("/health", _health, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/head", _head, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/bundle", _bundle, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/sync", _sync, methods=["POST"]),
    Route(
        "/api/v1/articles/{article_id}/ancestor/{hash}",
        _ancestor,
        methods=["GET"],
    ),
    Route("/api/v1/articles", _push_article_repo_handler, methods=["POST"]),
    Route("/api/v1/users/{user_id}/following", _following, methods=["GET"]),
    Route("/api/v1/users/{user_id}/followers", _followers, methods=["GET"]),
    Route("/api/v1/users/{user_id}/articles", _articles, methods=["GET"]),
    Route("/api/v1/users/{user_id}/bookmarks", _bookmarks, methods=["GET"]),
    Route("/api/v1/users/{user_id}/follow", _follow, methods=["POST"]),
    Route("/api/v1/users/{user_id}/unfollow", _unfollow, methods=["POST"]),
    Route("/api/v1/users/{user_id}/bookmark", _bookmark, methods=["POST"]),
]


def create_app() -> Starlette:
    """Build the Starlette ASGI app with all routes, middleware, and error handlers.

    Routes are defined in ``_ROUTES``; exception handlers map known
    ``PeerpediaError`` types (plus ``ValueError``, ``TypeError``,
    ``FileNotFoundError``, and ``GitCommandError``) to ``_error_handler``.
    ``Exception`` itself is intentionally NOT registered — Starlette routes
    it to ``ServerErrorMiddleware`` which always re-raises after handling.
    """
    handlers = {k: _error_handler for k in _ERROR_MAP}

    app = Starlette(
        routes=_ROUTES,
        middleware=[Middleware(DBSessionMiddleware)],
        exception_handlers=handlers,
    )
    return app
