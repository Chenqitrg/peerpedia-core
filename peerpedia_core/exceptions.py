# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Semantic exceptions for PeerPedia business logic.

These exceptions carry NO HTTP concepts (no status codes, no headers).
Backend routes catch them and translate to HTTPException via the handler
registered in ``peerpedia_api.main``.
"""


class PeerpediaError(Exception):
    """Base for all PeerPedia business-logic errors."""

    def __init__(self, detail: str = ""):
        self.detail = detail


class NotFoundError(PeerpediaError):
    """Requested resource does not exist."""


class NotAuthorizedError(PeerpediaError):
    """User lacks permission for the requested action."""


class ConflictError(PeerpediaError):
    """Request conflicts with the current state of the resource."""


class BadRequestError(PeerpediaError):
    """Input is invalid or missing required data."""
