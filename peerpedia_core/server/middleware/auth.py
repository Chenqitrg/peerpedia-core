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

from peerpedia_core.core import create_user_stub, get_user, update_user_public_key
from peerpedia_core.transport.auth import verify_auth_header
from peerpedia_core.types import short_id


class AuthMiddleware(BaseHTTPMiddleware):
    """Verify ``Peerpedia`` auth header against stored Ed25519 public key.

    Runs AFTER ``DBSessionMiddleware`` so ``request.state.db`` is available
    for the public key lookup.
    """

    # Paths that are public suffixes (e.g. /api/v1/articles/{id}/head).
    # endswith prevents substring false-positives like "/repo" matching "/report".
    _PUBLIC_PREFIXES = ("/health", "/api/v1/school")
    # Read-only — public.  /articles is NOT public (drafts are private),
    # but is called without auth from peers; the handler filters by status.
    _PUBLIC_SUFFIXES = (
        "/head", "/bundle", "/sync", "/repo",
        "/following", "/followers", "/articles", "/shares",
    )
    _PUBLIC_CONTAINS = ("/ancestor/",)  # /api/v1/articles/{id}/ancestor/{hash}

    async def dispatch(self, request: Request, call_next):
        """Verify Ed25519 auth header or allow public routes through."""
        path = request.url.path

        if path.startswith(self._PUBLIC_PREFIXES):
            return await call_next(request)
        if path.endswith(self._PUBLIC_SUFFIXES):
            return await call_next(request)
        for fragment in self._PUBLIC_CONTAINS:
            if fragment in path:
                return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Peerpedia "):
            return self._unauthorized()

        db = getattr(request.state, "db", None)
        if db is None:
            return self._unauthorized()

        body = await request.body()

        # Self-contained verification — pubkey is in the header.
        result = verify_auth_header(
            auth_header, request.method, path, body=body,
        )
        if not result.ok:
            return self._unauthorized(detail=result.reason)
        user_id, pubkey_hex = result.user_id, result.pubkey_hex

        # TOFU: if user doesn't exist locally, create a stub.
        # The signature proves they control this key pair.
        user = get_user(db, user_id)
        if user is None:
            create_user_stub(
                db, user_id=user_id, name=short_id(user_id),
                public_key=pubkey_hex, salt="",
            )
            db.commit()
        elif user.public_key and user.public_key != pubkey_hex:
            update_user_public_key(db, user_id, pubkey_hex)
            db.commit()

        request.state.user_id = user_id
        return await call_next(request)

    def _unauthorized(self, detail: str = ""):
        body = {"error": "Authentication required", "status": 401}
        if detail:
            body["detail"] = detail
        return JSONResponse(body, status_code=401)
