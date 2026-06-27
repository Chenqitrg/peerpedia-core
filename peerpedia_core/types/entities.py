# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""P2P exchange types — convert JSON at the boundary.

Each type has a ``from_json`` classmethod so callers never manually
construct these from raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserExchange:
    id: str
    name: str
    address: str = ""
    reputation: dict[str, float] | None = None

    @classmethod
    def from_json(cls, d: dict) -> UserExchange:
        return cls(
            id=d["id"], name=d.get("name", d["id"]), address=d.get("address", ""),
            reputation=d.get("reputation"),
        )



@dataclass(frozen=True)
class FollowExchange:
    id: str

    @classmethod
    def from_json(cls, d: dict) -> FollowExchange:
        return cls(id=d["id"])


@dataclass(frozen=True)
class ArticleMetaExchange:
    """Frozen projection of article metadata — P2P transfer and pure-logic input.

    Serves as the single immutable data contract for:
    - P2P article discovery (``from_json`` / ``to_json``)
    - Authorization rules (``rules/``)
    - Scoring / reputation algorithms (``compute/``)
    """
    id: str
    title: str
    status: str
    authors: tuple[str, ...] = ()
    score: dict[str, float] | None = None
    publish_consents: tuple[str, ...] | None = None

    @classmethod
    def from_json(cls, d: dict) -> ArticleMetaExchange:
        return cls(
            id=d["id"], title=d["title"], status=d["status"],
            authors=tuple(d.get("authors", [])),
            score=d.get("score"),
            publish_consents=tuple(d["publish_consents"]) if d.get("publish_consents") else None,
        )



@dataclass(frozen=True)
class ReviewExchange:
    """A single review — frozen projection for P2P and pure logic."""
    reviewer_id: str
    scores: dict[str, float]
    is_self: bool = False
    scope: str = ""
    status: str = ""

    @classmethod
    def from_json(cls, d: dict) -> ReviewExchange:
        return cls(
            reviewer_id=d["reviewer_id"], scores=d["scores"],
            is_self=d.get("is_self", False),
            scope=d.get("scope", ""), status=d.get("status", ""),
        )


@dataclass(frozen=True)
class BookmarkExchange:
    article_id: str

    @classmethod
    def from_json(cls, d: dict) -> BookmarkExchange:
        return cls(article_id=d["article_id"])


@dataclass(frozen=True)
class MaintainerExchange:
    user_id: str

    @classmethod
    def from_json(cls, d: dict) -> MaintainerExchange:
        return cls(user_id=d["user_id"])


@dataclass(frozen=True)
class ShareExchange:
    article_id: str
    recipient_id: str = ""
    comment: str = ""

    @classmethod
    def from_json(cls, d: dict) -> ShareExchange:
        return cls(article_id=d["article_id"],
                   recipient_id=d.get("recipient_id", ""),
                   comment=d.get("comment", ""))


@dataclass(frozen=True)
class NotificationExchange:
    event: str
    message: str
    id: str = ""
    article_id: str = ""
    actor_id: str = ""
    read: bool = False

    @classmethod
    def from_json(cls, d: dict) -> NotificationExchange:
        return cls(event=d["event"], message=d["message"],
                   id=d.get("id", ""), article_id=d.get("article_id", ""),
                   actor_id=d.get("actor_id", ""), read=bool(d.get("read", False)))
