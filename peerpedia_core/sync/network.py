# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Network reachability detection.

Pings the remote server health endpoint to determine online/offline status.
"""

from __future__ import annotations

import httpx


def is_online(server_url: str, timeout: float = 5.0) -> bool:
    """Return True if the remote server is reachable.

    Args:
        server_url: Base URL of the PeerPedia server (e.g. "https://peerpedia.dev").
        timeout: Request timeout in seconds.
    """
    try:
        response = httpx.get(f"{server_url}/health", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False
