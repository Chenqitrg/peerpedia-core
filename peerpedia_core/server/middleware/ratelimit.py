# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Simple in-memory rate limiter — per-IP, sliding-window.

Defaults from ``params.server.rate_limit_*``.  Returns ``429`` when
exceeded.  State is in-memory — restart clears all.
"""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from peerpedia_core.config.params import params


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject clients that exceed the rate limit.

    Per-IP sliding window — the first request outside the window resets
    the counter.  No persistent storage — restart clears all state.
    """

    def __init__(self, app,
                 max_requests: int | None = None,
                 window: int | None = None):
        super().__init__(app)
        self._max = max_requests if max_requests is not None else params.server.rate_limit_requests_per_window
        self._window = window if window is not None else params.server.rate_limit_window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    @staticmethod
    def _client_ip(request: Request) -> str:
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next):
        ip = self._client_ip(request)
        # Prune stale timestamps, then record this hit.
        now = time.monotonic()
        self._buckets[ip] = [t for t in self._buckets[ip] if now - t < self._window]
        self._buckets[ip].append(now)

        if len(self._buckets[ip]) > self._max:
            return JSONResponse(
                {"error": "Rate limit exceeded", "status": 429},
                status_code=429,
            )
        return await call_next(request)
