# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Canonical article status values and status-tag parsing.

Import from here instead of hardcoding status strings in individual modules.
The ``parse_status_tag`` function is the single parser for ``[status]``
markers in platform commit messages — used by both ``app/commands/bundle.py``
and integrity checking without creating a circular import.
"""

from __future__ import annotations

from enum import Enum

from peerpedia_core.config.params import PLATFORM_EMAIL


class ArticleStatus(str, Enum):
    """Canonical article lifecycle statuses.

    A ``str`` subclass so status values work as drop-in replacements for
    the raw strings used in DB columns, JSON serialisation, and comparisons.
    """

    DRAFT = "draft"
    SEDIMENTATION = "sedimentation"
    PUBLISHED = "published"
    REJECTED = "rejected"


VALID_ARTICLE_STATUSES = frozenset(s.value for s in ArticleStatus)
_VALID_STATUSES = set(VALID_ARTICLE_STATUSES)


def is_platform_commit(author_email: str) -> bool:
    """Return True if the commit was authored by the PeerPedia platform."""
    return author_email == PLATFORM_EMAIL


def parse_status_tag(message: str, author_email: str) -> str | None:
    """Return the article status if *message* is a valid platform status commit.

    Only accepts commits authored by the PeerPedia platform
    (``system@peerpedia``) whose message has the form ``[status] <valid_status>``.
    """
    if not is_platform_commit(author_email):
        return None
    msg = message.strip()
    prefix = "[status] "
    if not msg.startswith(prefix):
        return None
    status = msg[len(prefix):]
    return status if status in _VALID_STATUSES else None
