# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared utilities used by route handlers.

Currently only ``_validate_id`` — rejects non-UUID path parameters
to prevent path traversal attacks.  All article/user route handlers
call this before touching the filesystem or DB.
"""

import re

from peerpedia_core.exceptions import BadRequestError

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _validate_id(value: str, label: str) -> None:
    """Raise BadRequestError if *value* is not a valid UUID."""
    if not _UUID_RE.match(value):
        raise BadRequestError(f"Invalid {label}: {value[:50]!r}")
