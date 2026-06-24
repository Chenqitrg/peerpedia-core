# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ed25519 request-signing auth middleware.

Every authenticated request carries an ``Authorization`` header::

    Peerpedia <user_id>:<timestamp>:<body_sha256_hex>:<signature_hex>

The signature covers ``<method>:<path>:<user_id>:<ts>:<body_hash>``.
The body hash prevents tampering — replaying a signed header with a
different body will fail verification.  For GET requests, body_hash is "".

This middleware runs AFTER ``DBSessionMiddleware`` so ``request.state.db``
is available to look up the user's public key.  On success,
``request.state.user_id`` is set for downstream handlers.

Public routes (no auth required)
    Bundle sync endpoints — authenticated via Ed25519 commit signatures
    on the git objects themselves:
    ``/health``, ``/head``, ``/bundle``, ``/sync``, ``/ancestor/**``,
    ``/repo``.

If a public key is not found for the claimed user, or the signature is
invalid, returns ``401 {"error": "Authentication required"}``.
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
    _PUBLIC_PATHS = ("/head", "/bundle", "/sync", "/ancestor/", "/repo")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith(self._PUBLIC_PREFIXES):
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

        # Read the body for signature verification, then make it available
        # to the route handler via request.state.body.
        body = await request.body()

        result = verify_auth_header(
            auth_header,
            request.method,
            path,
            user.public_key,
            body=body,
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
