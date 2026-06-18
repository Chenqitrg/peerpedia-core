# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Cleaned database models — 7 entities matching the redesign spec.

Article content is stored in git repos (~/.peerpedia/articles/{id}/).
Database stores metadata, scores, relationships, and compilation cache.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from peerpedia_core.storage.db.engine import Base, JSONDict, JSONList


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Article ──────────────────────────────────────────────────────────────


class Article(Base):
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=_new_id)
    title = Column(String, nullable=False, default="")
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList, nullable=True)
    categories = Column(JSONList, nullable=True)
    status = Column(String, nullable=False, default="draft")  # draft|sedimentation|published
    score = Column(JSONDict, nullable=True)  # FiveDimScores as dict
    compiled_format = Column(String, nullable=True)  # "html" | "svg"
    compiled_output = Column(String, nullable=True)  # single-page result
    compiled_pages = Column(JSONList, nullable=True)  # list[str] for multi-page SVG
    sink_start = Column(DateTime, nullable=True)
    sink_duration_days = Column(Integer, nullable=False, default=7)
    sink_extended_count = Column(Integer, nullable=False, default=0)
    forked_from = Column(String, nullable=True)
    fork_count = Column(Integer, nullable=False, default=0)
    last_author_rebuild_hash = Column(String, nullable=True)  # HEAD commit hash of last author rebuild
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


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
    scope = Column(String, nullable=False)  # "pool" | "published"
    scores = Column(JSONDict, nullable=False)  # FiveDimScores as dict
    contributions = Column(JSONDict, nullable=True)  # author_id → 5-dim ratios
    thread = Column(JSONList, nullable=False, default=list)  # list[dict] of ThreadMessage
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


# ── ArticleAuthor (join table) ────────────────────────────────────────────


class ArticleAuthor(Base):
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id", name="uq_article_author"),)

    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    author_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    position = Column(Integer, default=0)


# ── User ─────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_new_id)
    username = Column(String, unique=True, nullable=False)  # login identifier
    password_hash = Column(String, nullable=False)  # bcrypt hash
    email = Column(String, nullable=True)  # format-validated
    name = Column(String, nullable=False)
    anonymous_name = Column(String, nullable=False, default="")
    affiliation = Column(String, nullable=False, default="")
    expertise = Column(JSONList, nullable=False, default=list)
    avatar_url = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    reputation = Column(JSONDict, nullable=False, default=dict)  # ReputationScores as dict
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ── Follow ───────────────────────────────────────────────────────────────


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "followed_id", name="uq_follow"),)

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
    fork_article_id = Column(String, ForeignKey("articles.id"), nullable=False)
    target_article_id = Column(String, ForeignKey("articles.id"), nullable=False)
    proposer_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="open")  # open|accepted|rejected
    thread = Column(JSONList, nullable=False, default=list)  # list[dict] of ThreadMessage
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ── Citation ─────────────────────────────────────────────────────────────


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("from_article_id", "to_article_id", name="uq_citation"),)

    from_article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    to_article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    forward_prob = Column(Float, nullable=False, default=0.0)
    backward_prob = Column(Float, nullable=False, default=0.0)
