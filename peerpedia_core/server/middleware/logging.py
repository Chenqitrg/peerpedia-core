# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Request audit logging middleware.

Attaches a ``Server-Time`` header (Unix timestamp) to every response for
client-side clock sync verification.  Only logs requests slower than
``params.server.log_slow_request_ms`` — default 500 ms.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from peerpedia_core.config.params import params

logger = logging.getLogger(__name__)

_MS_PER_SEC = 1000


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Attach Server-Time header; log slow requests."""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * _MS_PER_SEC

        response.headers["Server-Time"] = str(int(time.time()))

        if elapsed_ms >= params.server.log_slow_request_ms:
            logger.warning(
                "SLOW %s %s → %d (%.0fms)",
                request.method, request.url.path,
                response.status_code, elapsed_ms,
            )
        return response
