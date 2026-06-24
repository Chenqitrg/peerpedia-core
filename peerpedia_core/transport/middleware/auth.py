# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ed25519 request-signing auth middleware.

Authenticated requests carry ``Authorization: Peerpedia <uid>:<ts>:<sig>``.
The middleware verifies the signature against the user's Ed25519 public key
(loaded from the local DB via the DB session middleware, which runs first).

Public routes (no auth required):
    ``/health``, bundle sync endpoints (authenticated via commit signatures
    on the git objects themselves), and first-time article push.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from peerpedia_core.commands import get_user
from peerpedia_core.transport.auth import verify_auth_header


class AuthMiddleware(BaseHTTPMiddleware):
    """Verify ``Peerpedia`` auth header against stored Ed25519 public key.

    Runs AFTER ``DBSessionMiddleware`` so ``request.state.db`` is available
    for the public key lookup.
    """

    _PUBLIC_PREFIXES = ("/health",)
    _PUBLIC_ROUTES = frozenset({"/api/v1/articles"})
    _PUBLIC_PATHS = ("/head", "/bundle", "/sync", "/ancestor/")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self._PUBLIC_ROUTES or path.startswith(self._PUBLIC_PREFIXES):
            return await call_next(request)
        for fragment in self._PUBLIC_PATHS:
            if fragment in path:
                return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Peerpedia "):
            return self._unauthorized()

        # DB session must be available (DBSessionMiddleware runs first).
        db = getattr(request.state, "db", None)
        if db is None:
            return self._unauthorized()

        # Extract user_id from header to look up the public key.
        try:
            _, payload = auth_header.split(" ", 1)
            user_id = payload.split(":")[0]
        except ValueError:
            return self._unauthorized()

        user = get_user(db, user_id)
        if user is None or not user.public_key:
            return self._unauthorized()

        result = verify_auth_header(
            auth_header,
            request.method,
            path,
            user.public_key,
        )
        if result is None:
            return self._unauthorized()

        request.state.user_id = result
        return await call_next(request)

    def _unauthorized(self):
        return JSONResponse(
            {"error": "Authentication required", "status": 401},
            status_code=401,
        )
