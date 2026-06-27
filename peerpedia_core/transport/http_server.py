# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""ASGI app factory for the PeerPedia HTTP server — Starlette + SQLite.

This file assembles the server: health check, error mapping, middleware
stack, route table.  Everything else lives in submodules so this file
stays under 150 lines.

Architecture
------------
::

    Request → RateLimitMiddleware → AuditLogMiddleware
            → DBSessionMiddleware    (creates SQLite session per request)
            → AuthMiddleware         (Ed25519 signature verification)
            → Route handler          (thin wrapper → business logic)
            → _error_handler         (exception → HTTP status code)

Middleware order is significant: rate-limiting first (reject floods),
then audit logging (record everything), then DB session (so auth can
look up public keys), then auth (so routes see ``request.state.user_id``).

Route table
-----------
Bundle (public — auth via commit signatures, not HTTP)
    ``GET  /api/v1/articles/{id}/head``          git HEAD hash
    ``GET  /api/v1/articles/{id}/bundle?since=``  incremental git bundle
    ``POST /api/v1/articles/{id}/sync``           apply incoming bundle
    ``GET  /api/v1/articles/{id}/ancestor/{hash}`` is-ancestor probe
    ``POST /api/v1/articles``                     first-time repo upload (tar.gz)
    ``GET  /api/v1/articles/{id}/repo``           first-time repo download (tar.gz)
    ``GET  /api/v1/articles/{id}/history``         commit history

Content (authenticated)
    ``GET  /api/v1/articles/{id}``                article metadata
    ``GET  /api/v1/articles/{id}/source``          markdown/typst source

Users (authenticated)
    ``GET  /api/v1/users/{id}/following``          who this user follows
    ``GET  /api/v1/users/{id}/followers``          who follows this user
    ``GET  /api/v1/users/{id}/articles``           articles by this user
    ``POST /api/v1/users/{id}/follow``             follow a user
    ``POST /api/v1/users/{id}/unfollow``           unfollow a user

Discovery (authenticated)
    ``GET  /api/v1/search?q=&status=&limit=&offset=``  article search

Infrastructure (public)
    ``GET  /health``                              liveness probe

Error handling
--------------
Every ``PeerpediaError`` subclass maps to a specific HTTP status code.
``ValueError`` and ``TypeError`` map to 400 but are logged as warnings
(they may be internal bugs).  Tracebacks are included in the response
body ONLY when ``PEERPEDIA_DEBUG=true``.

Local integrity
---------------
``PEERPEDIA_SKIP_AUTH=true`` disables the auth middleware (for tests).
``PEERPEDIA_DEBUG=true`` enables traceback in error responses.

TODO(discovery): Implement auto peer discovery so new users don't need
an out-of-band server URL.  Three concrete steps:

  1. Auto-connect to seed peers on startup (params.py already has seed list).
     In ``_cmd_server_start``, spawn a background task that calls
     ``merge_peers(seed_url)`` for each seed, then ``fetch_peers`` from
     discovered peers, iterating up to ``max_known_peers``.

  2. Add ``POST /api/v1/peers`` route — peers announce themselves.
     When server A connects to server B, B adds A to its known_peers list.

  3. Auto-sync on startup: after bootstrap or login, call ``_try_sync``
     and ``_pull_social`` against each known peer, not just PEERPEDIA_SERVER.
     Files: cli/handlers/server.py, transport/routes/peers.py,
     cli/handlers/account.py (_cmd_bootstrap).
"""

from __future__ import annotations

import logging
import os
import traceback

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from peerpedia_core.core import db_repl_setup, health_check
from peerpedia_core.config.paths import DB_URL
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
from peerpedia_core.transport.middleware import AuthMiddleware, DBSessionMiddleware
from peerpedia_core.transport.middleware.logging import AuditLogMiddleware
from peerpedia_core.transport.middleware.ratelimit import RateLimitMiddleware
from peerpedia_core.transport.routes import ALL_ROUTES

logger = logging.getLogger(__name__)
DEBUG = bool(os.environ.get("PEERPEDIA_DEBUG"))


# ═══════════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════════


def _health(request: Request) -> JSONResponse:
    """GET /health → 200 if dependencies are reachable, 503 otherwise."""
    problems = health_check(DB_URL)
    if problems:
        return JSONResponse(
            {"status": "degraded", "problems": problems}, status_code=503
        )
    return JSONResponse({"status": "ok"})


# ═══════════════════════════════════════════════════════════════════════════════
# Error handling
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

try:
    import git as _git
    _ERROR_MAP[_git.GitCommandError] = 500
except ImportError:
    pass  # git not available — GitCommandError never raised


async def _error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a raised exception to an HTTP status code and JSON error body.

    Generic exceptions (ValueError, TypeError) that map to 400 are logged
    as warnings — they may be client errors or internal bugs.
    """
    status_code = 500
    for exc_type, code in _ERROR_MAP.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    if status_code == 500:
        logger.error("Internal server error", exc_info=exc)
    elif status_code == 400 and not isinstance(exc, PeerpediaError):
        logger.warning("Possible internal bug masked as 400", exc_info=exc)

    body: dict = {"error": str(exc), "status": status_code}
    if status_code == 500 and DEBUG:
        body["traceback"] = traceback.format_exc()

    return JSONResponse(body, status_code=status_code)


# ═══════════════════════════════════════════════════════════════════════════════
# App factory
# ═══════════════════════════════════════════════════════════════════════════════

_ROUTES = ALL_ROUTES + [Route("/health", _health, methods=["GET"])]


def create_app() -> Starlette:
    """Build the Starlette ASGI app with all routes, middleware, and error handlers."""
    # Init DB + apply migrations via the storage facade (not directly).
    db_repl_setup(DB_URL)

    handlers = {k: _error_handler for k in _ERROR_MAP}

    middleware = [
        Middleware(RateLimitMiddleware),
        Middleware(AuditLogMiddleware),
        Middleware(DBSessionMiddleware),
    ]
    if not os.environ.get("PEERPEDIA_SKIP_AUTH"):
        middleware.append(Middleware(AuthMiddleware))

    app = Starlette(
        routes=_ROUTES,
        middleware=middleware,
        exception_handlers=handlers,
    )
    return app
