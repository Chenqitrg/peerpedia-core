# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Database models — 8 entities.

Column-level ``: Type`` annotations document the Python-side type for each
column.  The ORM column types (``JSONDict``, ``JSONList``) are SQLite storage
details; the annotations are the domain types.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from peerpedia_core.storage.db.engine import Base, JSONDict, JSONList
from peerpedia_core.types.entities import (
    ArticleMetaExchange, NotificationExchange, ReviewExchange, ShareExchange, UserExchange,
)
from peerpedia_core.types.status import ArticleStatus


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── ArticleMetaStorage ──────────────────────────────────────────────────────────────


class ArticleMetaStorage(Base):
    """An academic article — content in git, metadata in DB.

    State machine: ``draft`` → ``sedimentation`` → ``published``.
    """
    __tablename__ = "articles"

    id: str = Column(String, primary_key=True, default=_new_id)
    title: str = Column(String, nullable=False)
    abstract: str | None = Column(String, nullable=True)
    keywords: list[str] | None = Column(JSONList, nullable=True)
    categories: list[str] | None = Column(JSONList, nullable=True)
    status: ArticleStatus = Column(String, nullable=False, default=ArticleStatus.DRAFT, index=True)
    score: dict[str, float] | None = Column(JSONDict, nullable=True)  # FiveDimScores
    publish_consents: list[str] | None = Column(JSONList, nullable=True)
    compiled_format: str | None = Column(String, nullable=True)
    compiled_output: str | None = Column(String, nullable=True)
    compiled_pages: list[str] | None = Column(JSONList, nullable=True)
    sink_start: datetime | None = Column(DateTime, nullable=True)
    sink_duration_days: int = Column(Integer, nullable=False, default=7)
    sink_extended_count: int = Column(Integer, nullable=False, default=0)
    total_sink_days_accumulated: float = Column(Float, nullable=False, default=0.0)
    forked_from: str | None = Column(String, nullable=True, index=True)
    fork_count: int = Column(Integer, nullable=False, default=0)
    last_author_rebuild_hash: str | None = Column(String, nullable=True)
    witnessed_at: datetime | None = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    updated_at: datetime = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "categories": self.categories,
            "status": self.status,
            "forked_from": self.forked_from,
            "fork_count": self.fork_count,
            "sink_start": str(self.sink_start) if self.sink_start else None,
            "sink_duration_days": self.sink_duration_days,
            "created_at": str(self.created_at) if self.created_at else None,
            "witnessed_at": str(self.witnessed_at) if self.witnessed_at else None,
        }

    @classmethod
    def from_exchange(cls, e: ArticleMetaExchange) -> dict[str, object]:
        result: dict[str, object] = {"id": e.id, "title": e.title, "status": e.status}
        if e.abstract is not None:
            result["abstract"] = e.abstract
        if e.score is not None:
            result["score"] = e.score
        if e.publish_consents is not None:
            result["publish_consents"] = list(e.publish_consents)
        return result

    def to_exchange(self) -> ArticleMetaExchange:
        return ArticleMetaExchange(
            id=self.id, title=self.title, status=self.status,
            abstract=self.abstract,
            score=self.score,
            publish_consents=tuple(self.publish_consents) if self.publish_consents else None,
        )


# ── ReviewMetaStorage ───────────────────────────────────────────────────────────────


class ReviewMetaStorage(Base):
    """A peer review — cached in DB after git commit."""
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash",
                         name="uq_review_article_reviewer_scope_commit"),
    )

    id: str = Column(String, primary_key=True, default=_new_id)
    article_id: str = Column(String, ForeignKey("articles.id"), nullable=False)
    commit_hash: str = Column(String, nullable=False)
    reviewer_id: str = Column(String, ForeignKey("users.id"), nullable=False)
    scope: str = Column(String, nullable=False)
    status: ArticleStatus = Column(String, nullable=False, default="submitted", server_default="'submitted'")
    scores: dict[str, float] = Column(JSONDict, nullable=False)  # FiveDimScores
    invited_by: str | None = Column(String, nullable=True)
    invited_at: datetime | None = Column(DateTime, nullable=True)
    helpfulness_score: int | None = Column(Integer, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    updated_at: datetime = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    @classmethod
    def from_exchange(cls, e: ReviewExchange) -> dict[str, object]:
        return {
            "reviewer_id": e.reviewer_id, "scores": e.scores,
            "scope": e.scope, "status": e.status,
        }

    def to_exchange(self) -> ReviewExchange:
        return ReviewExchange(
            reviewer_id=self.reviewer_id, scores=self.scores,
            is_self=False, scope=self.scope, status=self.status,
        )


# ── ArticleAuthorStorage (join table) ────────────────────────────────────────────


class ArticleAuthorStorage(Base):
    """Who *contributed* to an article (derived from git commit authors)."""
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id", name="uq_article_author"),)

    article_id: str = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    author_id: str = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    position: int = Column(Integer, default=0)


# ── ScriptMaintainerStorage (join table) ─────────────────────────────────────────


class ScriptMaintainerStorage(Base):
    """Who *manages* an article (edit/delete/publish/sync)."""
    __tablename__ = "script_maintainers"
    __table_args__ = (UniqueConstraint("article_id", "user_id", name="uq_script_maintainer"),)

    article_id: str = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    user_id: str = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)


# ── UserStorage ─────────────────────────────────────────────────────────────────


class UserStorage(Base):
    """A peer in the network — Ed25519 identity from password+salt."""
    __tablename__ = "users"

    id: str = Column(String, primary_key=True)
    name: str = Column(String, unique=False, nullable=False)
    public_key: str | None = Column(String, nullable=True)
    salt: str | None = Column(String, nullable=True)
    address: str | None = Column(String, nullable=True)
    last_fetch_at: datetime | None = Column(DateTime, nullable=True)
    affiliation: str = Column(String, nullable=False, default="")
    expertise: list[str] = Column(JSONList, nullable=False, default=list)
    avatar_url: str | None = Column(String, nullable=True)
    reputation: dict[str, float] = Column(JSONDict, nullable=False, default=dict)  # ReputationScores
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    failed_login_attempts: int = Column(Integer, nullable=False, default=0)
    locked_until: datetime | None = Column(DateTime, nullable=True)
    deleted_at: datetime | None = Column(DateTime, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "public_key": self.public_key,
            "affiliation": self.affiliation,
            "expertise": self.expertise,
            "avatar_url": self.avatar_url,
            "last_fetch_at": str(self.last_fetch_at) if self.last_fetch_at else None,
            "created_at": str(self.created_at) if self.created_at else None,
        }

    @classmethod
    def from_exchange(cls, e: UserExchange) -> dict[str, object]:
        result: dict[str, object] = {"id": e.id, "name": e.name, "address": e.address}
        if e.reputation is not None:
            result["reputation"] = e.reputation
        return result

    def to_exchange(self) -> UserExchange:
        return UserExchange(
            id=self.id, name=self.name, address=self.address or "",
            reputation=self.reputation if self.reputation else None,
        )


# ── FollowStorage ───────────────────────────────────────────────────────────────


class FollowStorage(Base):
    """Directed edge: *follower_id* follows *followed_id*."""
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="uq_follow"),
        CheckConstraint("follower_id != followed_id", name="ck_no_self_follow"),
    )

    follower_id: str = Column(String, ForeignKey("users.id"), primary_key=True)
    followed_id: str = Column(String, ForeignKey("users.id"), primary_key=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    deleted_at: datetime | None = Column(DateTime, nullable=True)


# ── AliasStorage ───────────────────────────────────────────────────────────────────


class AliasStorage(Base):
    """Local alias for a followed user — solves P2P name collision."""
    __tablename__ = "aliases"
    __table_args__ = (UniqueConstraint("owner_id", "alias", name="uq_alias"),)

    owner_id: str = Column(String, ForeignKey("users.id"), primary_key=True)
    target_id: str = Column(String, ForeignKey("users.id"), primary_key=True)
    alias: str = Column(String, nullable=False)


# ── ShareStorage ────────────────────────────────────────────────────────────────────


class ShareStorage(Base):
    """Public share — user recommends an article to followers."""
    __tablename__ = "shares"
    __table_args__ = (UniqueConstraint("sharer_id", "article_id", name="uq_share"),)

    id: str = Column(String, primary_key=True, default=_new_id)
    sharer_id: str = Column(String, ForeignKey("users.id"), nullable=False)
    article_id: str = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    recipient_id: str | None = Column(String, ForeignKey("users.id"), nullable=True)
    comment: str | None = Column(String, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    @classmethod
    def from_exchange(cls, e: ShareExchange) -> dict[str, object]:
        return {"article_id": e.article_id, "recipient_id": e.recipient_id or None,
                "comment": e.comment or None}

    def to_exchange(self) -> ShareExchange:
        return ShareExchange(article_id=self.article_id,
                             recipient_id=self.recipient_id or "",
                             comment=self.comment or "")


# ── BookmarkStorage ─────────────────────────────────────────────────────────────


class BookmarkStorage(Base):
    """Private bookmark — saved for later, not shared via P2P."""
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_bookmark"),)

    user_id: str = Column(String, ForeignKey("users.id"), primary_key=True)
    article_id: str = Column(String, ForeignKey("articles.id"), primary_key=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)


# ── NotificationStorage ──────────────────────────────────────────────────────────


class NotificationStorage(Base):
    """Local notification — emitted at event points, synced via P2P."""
    __tablename__ = "notifications"

    id: str = Column(String, primary_key=True, default=_new_id)
    user_id: str = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    event: str = Column(String, nullable=False)
    article_id: str | None = Column(String, ForeignKey("articles.id"), nullable=True)
    actor_id: str | None = Column(String, ForeignKey("users.id"), nullable=True)
    message: str = Column(String, nullable=False)
    read: int = Column(Integer, nullable=False, default=0)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event": self.event,
            "article_id": self.article_id,
            "actor_id": self.actor_id,
            "message": self.message,
            "read": self.read,
            "created_at": str(self.created_at) if self.created_at else None,
        }

    @classmethod
    def from_exchange(cls, e: NotificationExchange) -> dict[str, object]:
        return {"event": e.event, "message": e.message,
                "id": e.id or None, "article_id": e.article_id or None,
                "actor_id": e.actor_id or None, "read": 1 if e.read else 0,
                "created_at": e.created_at or None}

    def to_exchange(self) -> NotificationExchange:
        return NotificationExchange(event=self.event, message=self.message,
                                    id=self.id, article_id=self.article_id or "",
                                    actor_id=self.actor_id or "", read=bool(self.read),
                                    created_at=str(self.created_at) if self.created_at else "")


# ── MergeProposalStorage ────────────────────────────────────────────────────────


class MergeProposalStorage(Base):
    """Fork merge request: open → accepted/rejected."""
    __tablename__ = "merge_proposals"

    id: str = Column(String, primary_key=True, default=_new_id)
    fork_article_id: str = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    target_article_id: str = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    proposer_id: str = Column(String, ForeignKey("users.id"), nullable=False)
    status: ArticleStatus = Column(String, nullable=False, default="open")
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at: datetime | None = Column(DateTime, nullable=True)


# ── CitationStorage ─────────────────────────────────────────────────────────────


class CitationStorage(Base):
    """Directed citation edge with graph-topology probabilities."""
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("from_article_id", "to_article_id", name="uq_citation"),)

    from_article_id: str = Column(String, ForeignKey("articles.id"), primary_key=True)
    to_article_id: str = Column(String, ForeignKey("articles.id"), primary_key=True, index=True)
    forward_prob: float = Column(Float, nullable=False, default=0.0)
    backward_prob: float = Column(Float, nullable=False, default=0.0)
