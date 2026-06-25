# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared utilities used by route handlers.

Currently only ``_validate_id`` — rejects non-UUID path parameters
to prevent path traversal attacks.  All article/user route handlers
call this before touching the filesystem or DB.
"""

import re

from starlette.responses import JSONResponse

from peerpedia_core.exceptions import BadRequestError

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _validate_id(value: str, label: str) -> None:
    """Raise BadRequestError if *value* is not a valid UUID."""
    if not _UUID_RE.match(value):
        raise BadRequestError(f"Invalid {label}: {value[:50]!r}")


def _require_field(payload: dict, name: str) -> str:
    """Extract and validate a required field from a JSON payload.

    Raises BadRequestError if *name* is missing or empty.
    Returns the field value.
    """
    value = payload.get(name)
    if not value:
        raise BadRequestError(f"Missing required field: '{name}'")
    return value


def _ok_response(data: dict | None = None) -> JSONResponse:
    """Return a standard ``{"ok": True}`` response (or with extra data)."""
    body = {"ok": True}
    if data:
        body.update(data)
    return JSONResponse(body)


def _parse_pagination(request, default_limit: int = 20, max_limit: int = 100) -> tuple[int, int]:
    """Parse ``limit`` and ``offset`` query params from a Starlette request.

    Returns ``(limit, offset)`` — both clamped to safe ranges.
    """
    limit = min(int(request.query_params.get("limit", default_limit)), max_limit)
    offset = int(request.query_params.get("offset", 0))
    return limit, offset
