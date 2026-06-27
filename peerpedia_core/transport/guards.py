# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport-level guards — validate HTTP/P2P responses."""

from __future__ import annotations

from typing import Callable

from peerpedia_core.exceptions import ProtocolError, TransportError


def require_fetch_response(
    fetch_fn: Callable, server: str, user_id: str, label: str, **auth_kwargs,
) -> list[dict]:
    """Call *fetch_fn*, raise on failure or None response. Returns data."""
    try:
        data = fetch_fn(server, user_id, **auth_kwargs)
    except TransportError as e:
        raise ConnectionError(
            f"Failed to fetch {label} from {server} for {user_id}: {e.detail}"
        ) from e
    if data is None:
        raise ProtocolError(
            f"fetch_{label}: server {server} returned None for user {user_id}"
        )
    return data


