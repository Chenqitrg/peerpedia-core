# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Canonical article status values and status-tag parsing.

Import from here instead of hardcoding status sets in individual modules.
The ``parse_status_tag`` function is the single parser for ``[status]``
markers in platform commit messages — used by both ``commands/bundle.py``
and ``commands/integrity.py`` without creating a circular import.
"""

from __future__ import annotations

from peerpedia_core.config.params import PLATFORM_EMAIL

VALID_ARTICLE_STATUSES = frozenset({"draft", "sedimentation", "published", "rejected"})
_VALID_STATUSES = set(VALID_ARTICLE_STATUSES)


def parse_status_tag(message: str, author_email: str) -> str | None:
    """Return the article status if *message* is a valid platform status commit.

    Only accepts commits authored by the PeerPedia platform
    (``system@peerpedia``) whose message has the form ``[status] <valid_status>``.
    """
    if author_email != PLATFORM_EMAIL:
        return None
    msg = message.strip()
    prefix = "[status] "
    if not msg.startswith(prefix):
        return None
    status = msg[len(prefix):]
    return status if status in _VALID_STATUSES else None
