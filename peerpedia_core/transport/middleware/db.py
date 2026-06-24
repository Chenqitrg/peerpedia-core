# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""DB session middleware — creates a SQLite session per request.

Runs BEFORE ``AuthMiddleware`` so auth can look up the user's public key.
Default: inject a DB session for every request.  Only git-only routes
(head, bundle, ancestor, repo) are excluded — they only touch the
filesystem and don't need a DB connection.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Route

from peerpedia_core.commands import db_session
from peerpedia_core.config.paths import DB_URL


class DbRoute(Route):
    """Starlette ``Route`` with explicit DB-dependency declaration.

    ``needs_db`` (default ``True``) — set ``False`` for git-only routes
    that don't need a database session (e.g. head, bundle, repo).
    """

    def __init__(self, path: str, endpoint, *, needs_db: bool = True, **kwargs) -> None:
        super().__init__(path, endpoint, **kwargs)
        self.needs_db = needs_db


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Inject a DB session for every request except git-only routes.

    Git-only routes (head, bundle, ancestor, repo) are authenticated via
    Ed25519 commit signatures on the git objects themselves and never
    touch the database.

    Default-inject is the safe default — new routes get a DB session
    automatically; only routes that explicitly don't need one are excluded.
    """

    # Paths that do NOT need a DB session (git-only operations).
    _NO_DB_PREFIXES = ("/health",)
    _NO_DB_SUFFIXES = ("/head", "/bundle", "/repo")
    _NO_DB_CONTAINS = ("/ancestor/",)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        skip_db = (
            path.startswith(self._NO_DB_PREFIXES)
            or path.endswith(self._NO_DB_SUFFIXES)
            or any(fragment in path for fragment in self._NO_DB_CONTAINS)
        )
        if skip_db:
            return await call_next(request)

        with db_session(DB_URL) as db:
            request.state.db = db
            return await call_next(request)
