# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Cleaned database models — 7 entities matching the redesign spec.

Article content is stored in git repos (~/.peerpedia/articles/{id}/).
Database stores metadata, scores, relationships, and compilation cache.

.. todo::
   Split domain entities (Article, User, etc.) from ORM persistence.
   ``Column``, ``ForeignKey``, and ``Base`` are SQLAlchemy concerns that
   currently couple the domain model to the database layer.  The domain
   entities should live outside ``storage/`` and define their shape with
   plain types, not ORM column descriptors.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from peerpedia_core.storage.db.engine import Base, JSONDict, JSONList


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Article ──────────────────────────────────────────────────────────────


class Article(Base):
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=_new_id)
    title = Column(String, nullable=False)
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList, nullable=True)
    categories = Column(JSONList, nullable=True)
    # TODO(perf): missing index on status — filtered queries do full table scan.
    status = Column(String, nullable=False, default="draft")  # draft|sedimentation|published
    score = Column(JSONDict, nullable=True)  # FiveDimScores as dict
    compiled_format = Column(String, nullable=True)  # "html" | "svg"
    compiled_output = Column(String, nullable=True)  # single-page result
    compiled_pages = Column(JSONList, nullable=True)  # list[str] for multi-page SVG
    sink_start = Column(DateTime, nullable=True)
    sink_duration_days = Column(Integer, nullable=False, default=7)
    sink_extended_count = Column(Integer, nullable=False, default=0)
    # TODO(perf): missing index on forked_from — fork lookups scan all rows.
    forked_from = Column(String, nullable=True)
    fork_count = Column(Integer, nullable=False, default=0)
    last_author_rebuild_hash = Column(String, nullable=True)  # HEAD commit hash of last author rebuild
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        """Expose all article fields except internal caches (compiled_*, score)."""
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
        }


# ── Review ───────────────────────────────────────────────────────────────


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash", name="uq_review_article_reviewer_scope_commit"),
    )

    id = Column(String, primary_key=True, default=_new_id)
    article_id = Column(String, ForeignKey("articles.id"), nullable=False)
    commit_hash = Column(String, nullable=False)
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=False)
    scope = Column(String, nullable=False)  # "sedimentation" | "published" — matches article.status
    scores = Column(JSONDict, nullable=False)  # FiveDimScores as dict
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


# ── ArticleAuthor (join table) ────────────────────────────────────────────


class ArticleAuthor(Base):
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id", name="uq_article_author"),)

    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    # TODO(perf): composite PK does not cover author_id-only queries. Add
    # index=True so get_articles_by_author doesn't full-scan.
    author_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    position = Column(Integer, default=0)


# ── ScriptMaintainer (join table) ─────────────────────────────────────────


class ScriptMaintainer(Base):
    """Who *manages* an article (edit/delete/publish/sync).

    Orthogonal to ArticleAuthor: git history determines who *contributed*,
    this table determines who *manages*.  Maintainer is always explicitly
    granted — it is never derived from authorship.
    """
    __tablename__ = "script_maintainers"
    __table_args__ = (UniqueConstraint("article_id", "user_id", name="uq_script_maintainer"),)

    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ── User ─────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    # TODO(p2p): name unique constraint is incompatible with P2P — two peers
    # can independently register the same name.  Remove unique=True once
    # get_user_by_name / login / follow are updated to handle duplicates.
    name = Column(String, unique=True, nullable=False)
    public_key = Column(String, nullable=True)  # Ed25519 pubkey hex — set by register or TOFU
    salt = Column(String, nullable=True)  # hex-encoded scrypt salt (16 bytes)
    address = Column(String, nullable=True)  # peer URL
    last_fetch_at = Column(DateTime, nullable=True)  # metadata TTL
    affiliation = Column(String, nullable=False, default="")
    expertise = Column(JSONList, nullable=False, default=list)
    avatar_url = Column(String, nullable=True)
    reputation = Column(JSONDict, nullable=False, default=dict)  # ReputationScores as dict
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        """Expose user fields for peer exchange. Excludes salt (secret) and reputation (local)."""
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


# ── Follow ───────────────────────────────────────────────────────────────


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="uq_follow"),
        CheckConstraint("follower_id != followed_id", name="ck_no_self_follow"),
    )

    follower_id = Column(String, ForeignKey("users.id"), primary_key=True)
    followed_id = Column(String, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ── Bookmark ─────────────────────────────────────────────────────────────


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_bookmark"),)

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ── MergeProposal ────────────────────────────────────────────────────────


class MergeProposal(Base):
    __tablename__ = "merge_proposals"

    id = Column(String, primary_key=True, default=_new_id)
    # TODO(perf): missing indexes on target_article_id and fork_article_id —
    # delete_article and get_merge_proposals do full table scans.
    fork_article_id = Column(String, ForeignKey("articles.id"), nullable=False)
    target_article_id = Column(String, ForeignKey("articles.id"), nullable=False)
    proposer_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="open")  # open|accepted|rejected
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ── Citation ─────────────────────────────────────────────────────────────


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("from_article_id", "to_article_id", name="uq_citation"),)

    from_article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    # TODO(perf): composite PK does not cover to_article_id-only queries
    # (get_cited_by). Add index=True.
    to_article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    forward_prob = Column(Float, nullable=False, default=0.0)
    backward_prob = Column(Float, nullable=False, default=0.0)
