# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Minimal transfer types for P2P social graph exchange.

NOT ORM models — these carry only the fields needed for peer discovery
and ingest.  Deserialize JSON at the boundary, pass typed objects inward.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PeerUser:
    """A user as seen from a peer — minimal identity fields."""
    id: str
    name: str
    address: str = ""


@dataclass(frozen=True)
class FollowEntry:
    """A single follow edge from a peer."""
    id: str


@dataclass(frozen=True)
class ArticleStub:
    """Article metadata for peer discovery — not the full entity."""
    id: str
    title: str
    status: str
    authors: tuple[str, ...] = ()


@dataclass(frozen=True)
class BookmarkEntry:
    """A bookmark reference from a peer."""
    article_id: str


@dataclass(frozen=True)
class MaintainerEntry:
    """A maintainer reference from a peer."""
    user_id: str


@dataclass(frozen=True)
class ShareEntry:
    """A share event from a peer."""
    article_id: str
    recipient_id: str = ""
    comment: str = ""


@dataclass(frozen=True)
class NotificationEntry:
    """A notification payload from a peer."""
    event: str
    message: str
    id: str = ""
    article_id: str = ""
    actor_id: str = ""
    read: bool = False
