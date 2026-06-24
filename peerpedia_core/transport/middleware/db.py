# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""DB session middleware — creates a SQLite session per request."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from peerpedia_core.config.paths import DB_URL
from peerpedia_core.storage.db import db_session


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Create a DB session per request for routes that need it.

    Skips session creation for routes that only touch git or are static:
    ``/health``, article head/bundle/ancestor, and first-time article push.

    TODO(infra): URL prefix/suffix matching is fragile — a new route that
    needs DB but doesn't match the pattern silently gets no session.
    Use route-level middleware or explicit dependency declaration.
    """

    _DB_ROUTES = frozenset({"/api/v1/users", "/api/v1/search", "/api/v1/articles"})
    _DB_SUFFIXES = ("/sync",)

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
            return await call_next(request)
