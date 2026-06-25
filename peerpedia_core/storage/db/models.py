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
    """An academic article — the core entity.  Content lives in git; DB stores metadata, scores, and state.

    State machine: ``draft`` → ``sedimentation`` → ``published``.
    Status transitions are recorded as git commits (``[status] ...``) so
    they survive P2P sync without a consensus protocol.
    """
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=_new_id)
    title = Column(String, nullable=False)
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList, nullable=True)
    # TODO(tag-system): upgrade from flat JSONList to a wiki-style Tag entity.
    #
    # Tag model:
    #   Tag(id, name, description, canonical_id)
    #   canonical_id → Tag.id (nullable FK to self) — when set, this tag is
    #     a synonym/redirect to the canonical tag.  Queries resolve via
    #     WHERE COALESCE(canonical_id, id) = ?.
    #   ArticleTag(article_id, tag_id) — normalized join table replacing JSONList.
    #
    # Tag-tag relations (subfield_of, related_to, see_also) use the same
    # ArticleTag pattern: a TagRelation(from_tag_id, to_tag_id, relation_type)
    # table.  A tag becomes a subfield of another by adding a relation row —
    # no separate hierarchy model needed.
    #
    # Synonym detection (crowdsourced via publishing, not community patrol):
    #   1. At publish time, the author selects tags AND marks which ones they
    #      consider synonymous (e.g. "量子物理" ≈ "量子力学").  This is a
    #      TagSynonymVote(from_tag_id, to_tag_id, voter_id, article_id).
    #   2. Votes sync with the article bundle — every publication is a ballot.
    #   3. When enough distinct authors vote A ≈ B (threshold T, e.g. 5),
    #      auto-merge: A.canonical_id = B.id.  No central authority needed.
    #   4. Aliases persist — "量子物理" still exists, resolves to "量子力学".
    #
    # This turns tag governance from maintenance work into a byproduct of
    # publishing.  No dedicated patrolling, no central committee.
    # CLI: peerpedia tag merge <source> <target> (manual override)
    categories = Column(JSONList, nullable=True)
    status = Column(String, nullable=False, default="draft", index=True)  # draft|sedimentation|published
    score = Column(JSONDict, nullable=True)  # FiveDimScores as dict
    publish_consents = Column(JSONList, nullable=True)  # maintainer IDs who consented to publish/merge
    compiled_format = Column(String, nullable=True)  # "html" | "svg"
    compiled_output = Column(String, nullable=True)  # single-page result
    compiled_pages = Column(JSONList, nullable=True)  # list[str] for multi-page SVG
    sink_start = Column(DateTime, nullable=True)
    sink_duration_days = Column(Integer, nullable=False, default=7)
    sink_extended_count = Column(Integer, nullable=False, default=0)
    total_sink_days_accumulated = Column(Float, nullable=False, default=0.0)  # cumulative days from edits + extensions
    forked_from = Column(String, nullable=True, index=True)
    fork_count = Column(Integer, nullable=False, default=0)
    last_author_rebuild_hash = Column(String, nullable=True)  # HEAD commit hash of last author rebuild
    witnessed_at = Column(DateTime, nullable=True)  # server clock when a new commit arrived via sync — proves "existed by"
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
            "witnessed_at": str(self.witnessed_at) if self.witnessed_at else None,
        }


# ── Review ───────────────────────────────────────────────────────────────


class Review(Base):
    """A peer review — cached in DB after being committed to git.  Scores are five-dimensional (originality, rigor, completeness, pedagogy, impact)."""
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash", name="uq_review_article_reviewer_scope_commit"),
    )

    id = Column(String, primary_key=True, default=_new_id)
    article_id = Column(String, ForeignKey("articles.id"), nullable=False)
    commit_hash = Column(String, nullable=False)
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=False)
    scope = Column(String, nullable=False)  # "sedimentation" | "published" — matches article.status
    status = Column(String, nullable=False, default="submitted", server_default="'submitted'")  # "invited" | "accepted" | "declined" | "submitted"
    scores = Column(JSONDict, nullable=False)  # FiveDimScores as dict
    invited_by = Column(String, nullable=True)  # user_id of inviter (P0-3.5)
    invited_at = Column(DateTime, nullable=True)  # when invitation was sent
    helpfulness_score = Column(Integer, nullable=True)  # 1-5, author rating (P0-6)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


# ── ArticleAuthor (join table) ────────────────────────────────────────────


class ArticleAuthor(Base):
    """Join table: who *contributed* to an article (derived from git commit authors).  Orthogonal to ScriptMaintainer."""
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id", name="uq_article_author"),)

    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    author_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
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
    """A peer in the network.  Identity is an Ed25519 key pair derived from password+salt.

    ``public_key`` and ``salt`` are shareable via P2P sync.  ``salt`` is
    needed for key recovery on a new device.  ``name`` is NOT unique — two
    peers can independently register the same name (P2P compatibility).
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, unique=False, nullable=False)
    public_key = Column(String, nullable=True)  # Ed25519 pubkey hex — set by register or TOFU
    salt = Column(String, nullable=True)  # hex-encoded scrypt salt (16 bytes)
    address = Column(String, nullable=True)  # peer URL
    last_fetch_at = Column(DateTime, nullable=True)  # metadata TTL
    affiliation = Column(String, nullable=False, default="")
    expertise = Column(JSONList, nullable=False, default=list)
    avatar_url = Column(String, nullable=True)
    reputation = Column(JSONDict, nullable=False, default=dict)  # ReputationScores as dict
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    # Rate-limiting: brute-force protection on login
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    # Soft-delete: GDPR right-to-erasure. Follows Follow model pattern.
    deleted_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Expose user fields for peer exchange. Excludes salt (not synced — only needed locally) and reputation (local)."""
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
    """Directed social graph edge: *follower_id* follows *followed_id*.  Self-follow is prevented by check constraint."""
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="uq_follow"),
        CheckConstraint("follower_id != followed_id", name="ck_no_self_follow"),
    )

    follower_id = Column(String, ForeignKey("users.id"), primary_key=True)
    followed_id = Column(String, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    deleted_at = Column(DateTime, nullable=True)  # soft-delete for unfollow propagation


# ── Alias ───────────────────────────────────────────────────────────────────


class Alias(Base):
    """Local alias for a followed user — solves P2P name collision.

    Each *owner* can assign a unique *alias* to any user they follow.
    ``@alias`` resolves like ``@username`` but is locally scoped.
    """
    __tablename__ = "aliases"
    __table_args__ = (UniqueConstraint("owner_id", "alias", name="uq_alias"),)

    owner_id = Column(String, ForeignKey("users.id"), primary_key=True)
    target_id = Column(String, ForeignKey("users.id"), primary_key=True)
    alias = Column(String, nullable=False)


# ── Share ────────────────────────────────────────────────────────────────────


class Share(Base):
    """Public share/forward — a user recommends an article to followers.

    Unlike bookmarks (private), shares are visible to followers and can
    be directed (@recipient).  This is the primary content-discovery and
    moderation-signal mechanism.
    """
    __tablename__ = "shares"
    __table_args__ = (UniqueConstraint("sharer_id", "article_id", name="uq_share"),)

    id = Column(String, primary_key=True, default=_new_id)
    sharer_id = Column(String, ForeignKey("users.id"), nullable=False)
    article_id = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=True)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ── Bookmark ─────────────────────────────────────────────────────────────


class Bookmark(Base):
    """Private bookmark — a user saves an article for later.  Not shared via P2P social graph."""
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_bookmark"),)

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# ── Notification ──────────────────────────────────────────────────────────


class Notification(Base):
    """Local notification — informs a user about events on their articles or profile.

    Created by command functions at event emission points, synced via P2P
    so users on other devices see the same notifications.
    """
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    event = Column(String, nullable=False)  # review_submitted|merge_proposed|new_follower|article_published|review_invitation
    article_id = Column(String, ForeignKey("articles.id"), nullable=True)
    actor_id = Column(String, ForeignKey("users.id"), nullable=True)
    message = Column(String, nullable=False)
    read = Column(Integer, nullable=False, default=0)  # 0=unread, 1=read
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        """Serialize for P2P sync."""
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


# ── MergeProposal ────────────────────────────────────────────────────────


class MergeProposal(Base):
    """Tracks a request to merge a fork back into its origin article.  Status: open → accepted/rejected."""
    __tablename__ = "merge_proposals"

    id = Column(String, primary_key=True, default=_new_id)
    fork_article_id = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    target_article_id = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    proposer_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="open")  # open|accepted|rejected
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ── Citation ─────────────────────────────────────────────────────────────


class Citation(Base):
    """Directed citation edge between two articles.  ``forward_prob`` estimates P(cited | cites).

    Citation metadata (author, title, venue, year) lives in a ``.bib`` file
    inside the article's git repo — it is text, version-controlled, and
    reconstructable.  Only the two computed probabilities (*forward_prob*,
    *backward_prob*) need DB storage — they are graph-topology scores that
    cannot be recalculated from source alone.  This follows ADR-007: git is
    the SOT for content, DB caches only what cannot be reconstructed.
    """
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("from_article_id", "to_article_id", name="uq_citation"),)

    from_article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    to_article_id = Column(String, ForeignKey("articles.id"), primary_key=True, index=True)
    # TODO(citation-probs): forward_prob / backward_prob are the ONLY fields
    # that must live in DB.  Everything else (keys, authors, venues) should
    # be reconstructed from the .bib file in git, not cached here.
    forward_prob = Column(Float, nullable=False, default=0.0)
    backward_prob = Column(Float, nullable=False, default=0.0)
