# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Network reachability -- single function, no dependencies on other sync modules.

``is_online(server_url) -> bool``
    GET /health with a 5-second timeout.  Returns True if the server
    responds 200, False on any error (timeout, connection refused, DNS
    failure, non-200 status).  Used by ``cli.py`` to decide whether to
    show sync status or offer push.

    Swallows all exceptions -- the caller just needs a boolean.  This is
    intentional: network detection should never crash the app.

Reviewer's checklist
--------------------
- Is the timeout short enough that the CLI doesn't hang on startup?
  (5 seconds is fine for a health check.)
"""

from __future__ import annotations

import httpx


def is_online(server_url: str, timeout: float = 5.0) -> bool:
    """Return True if the remote server is reachable.

    All errors (timeout, DNS failure, connection refused, non-200) map to
    ``False``.  This is intentional — the caller only needs a boolean for
    a UI decision (show/hide sync badge), and a failed health check should
    never crash the app.

    Args:
        server_url: Base URL of the PeerPedia server (e.g. "https://peerpedia.dev").
        timeout: Request timeout in seconds.
    """
    try:
        response = httpx.get(f"{server_url}/health", timeout=timeout)
        return response.status_code == 200
    except httpx.HTTPError:
        return False
