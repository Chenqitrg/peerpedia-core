# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Inject a SQLite session into every request, except git-only routes.

Git-only routes (head, bundle, repo, ancestor) don't touch the database —
they operate directly on the filesystem.  All other routes get a DB session
attached to ``request.state.db``.

Runs BEFORE ``AuthMiddleware`` so auth can look up public keys.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from peerpedia_core.config.params import params
from peerpedia_core.config.paths import DB_URL
from peerpedia_core.core import db_session


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Insert a DB session per request, skip for git-only paths."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if (
            path.startswith(params.server.db_skip_prefixes)
            or path.endswith(params.server.db_skip_suffixes)
            or any(f in path for f in params.server.db_skip_contains)
        ):
            # Git-only route — no DB needed.
            return await call_next(request)

        with db_session(DB_URL) as db:
            request.state.db = db
            return await call_next(request)
