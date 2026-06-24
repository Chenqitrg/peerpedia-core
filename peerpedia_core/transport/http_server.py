# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""ASGI app factory for the PeerPedia HTTP server.

Thin shell — routes live in ``transport/routes/``, middleware in
``transport/middleware/``.  This file only assembles the app.

TODO(discovery): no bootstrap peer or server directory — new users must
know a server URL out-of-band.  Add a seed peer list or peer exchange
endpoint so the network is discoverable.
"""

from __future__ import annotations

import logging
import os
import traceback

import git as gitmod
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from peerpedia_core.config.paths import ARTICLES_DIR, DB_URL
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
from peerpedia_core.storage.db import db_session
from peerpedia_core.transport.middleware import AuthMiddleware, DBSessionMiddleware
from peerpedia_core.transport.middleware.logging import AuditLogMiddleware
from peerpedia_core.transport.routes import ALL_ROUTES

logger = logging.getLogger(__name__)
DEBUG = bool(os.environ.get("PEERPEDIA_DEBUG"))


# ═══════════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════════


def _health(request: Request) -> JSONResponse:
    """GET /health → 200 if dependencies are reachable, 503 otherwise."""
    problems: list[str] = []
    if not ARTICLES_DIR.is_dir():
        problems.append("articles_dir_missing")
    try:
        with db_session(DB_URL) as _:
            pass
    except Exception as e:
        problems.append(f"db_unreachable: {e}")

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

_ERROR_MAP[gitmod.GitCommandError] = 500


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
    handlers = {k: _error_handler for k in _ERROR_MAP}

    middleware = [
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
