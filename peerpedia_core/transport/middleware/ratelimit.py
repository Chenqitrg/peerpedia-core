# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Simple in-memory rate limiter — per-IP, sliding-window.

Defaults: 60 requests per 10‑second window per client IP.
Returns ``429`` when exceeded.  State is in-memory — restart clears all.
"""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Max requests per window per IP.  Generous for local/CLI use.
_MAX_REQUESTS = 60
_WINDOW_SECS = 10


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject clients that exceed the rate limit.

    Per-IP sliding window — the first request outside the window resets
    the counter.  No persistent storage — restart clears all state.
    """

    def __init__(self, app, max_requests: int = _MAX_REQUESTS, window: int = _WINDOW_SECS):
        super().__init__(app)
        self._max = max_requests
        self._window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        """Rate-limit by client IP; return 429 if exceeded."""
        ip = request.client.host if (request.client and request.client.host) else "unknown"
        now = time.monotonic()
        bucket = [t for t in self._buckets[ip] if now - t < self._window]
        bucket.append(now)
        self._buckets[ip] = bucket

        if len(bucket) > self._max:
            return JSONResponse(
                {"error": "Rate limit exceeded", "status": 429},
                status_code=429,
            )
        return await call_next(request)
