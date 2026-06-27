# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""P2P exchange types — minimal fields exchanged between peers.

NOT ORM models — deserialize JSON at the boundary, pass typed objects inward.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserExchange:
    id: str
    name: str
    address: str = ""


@dataclass(frozen=True)
class FollowExchange:
    id: str


@dataclass(frozen=True)
class ArticleMetaExchange:
    id: str
    title: str
    status: str
    authors: tuple[str, ...] = ()


@dataclass(frozen=True)
class BookmarkExchange:
    article_id: str


@dataclass(frozen=True)
class MaintainerExchange:
    user_id: str


@dataclass(frozen=True)
class ShareExchange:
    article_id: str
    recipient_id: str = ""
    comment: str = ""


@dataclass(frozen=True)
class NotificationExchange:
    event: str
    message: str
    id: str = ""
    article_id: str = ""
    actor_id: str = ""
    read: bool = False
