# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Immutable algorithm input — a DB snapshot that pure functions consume.

``ReputationState`` is the contract between the orchestrator (commands/)
and pure algorithms (workflow/).  Tests construct State directly — no DB.

Design constraint: the reputation algorithm MUST be replaceable without
changing anything else.  ``ReputationState`` is the single interface
that all algorithms (hand-written or ML) consume.

The performative prediction problem
-----------------------------------
Any reputation function *f* that scores content also shapes what gets created.
High-weight reviewers dominate scoring → their taste determines what scores
high → authors optimize for that taste → the reviewer stays high-weight.
This is NOT a bug — it is a property of any self-referential scoring system.

Mitigations (future):
  1. Random-exposure control group (5-10% of feed) to detect drift.
  2. Separate "content quality" (measured on controls) from "ranking score"
     (can be personalized).
  3. Fork the algorithm — if Alice disagrees with the current definition
     of quality, she can fork the reputation module.  Two definitions
     coexist; users choose which to trust.

There is no ground truth
------------------------
"Academic quality" is an institutional fact (Searle): it exists because a
community collectively treats it as real.  It is NOT a physical property
that can be measured with better instrumentation.  Every scoring system
— peer review, h-index, journal impact factor — is a social convention,
not a measurement.

PeerPedia does not claim to discover the "true" quality function.  It
provides a venue where competing definitions coexist, fork, and compete.
The architecture must support swapping the algorithm without changing
the rest of the system.  That is the purpose of this module.

Candidate observables (all measurable without human judgment)
-------------------------------------------------------------
The optimization target is itself part of the algorithm — and therefore
also forkable.  Examples of observable behaviors that could serve as
optimization targets:

  - Bookmark flow: total bookmark count weighted by article recency.
    Bookmarks signal "worth returning to" — a quality proxy that resists
    clickbait better than view count.

  - Re-read depth: Σ 5^n × dwell_time_n  for the n-th time a user opens
    the same article.  Exponential weighting (5→25→125→625) means one
    person who returned 4 times contributes more signal than 4 people
    who opened once and bounced.

  - Fork count: how many articles fork from this one.  Signals reusability.

  - Review-thread depth: average length of review discussions.  Signals
    that the article provokes substantive engagement.

  - Citation depth: weighted by the citing article's own score (PageRank
    on the citation graph).

Every choice of target produces a different academic ecosystem.  The
architecture does NOT pick one — it lets communities fork the target
function and compete, just like they fork the scoring function.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ArticleSnapshot:
    """A single article at the moment of extraction."""

    id: str
    score: dict | None  # FiveDimScores as dict, or None
    status: str
    author_ids: tuple[str, ...]
    review_count: int = 0


@dataclass(frozen=True)
class ReviewSnapshot:
    """A single review at the moment of extraction."""

    reviewer_id: str
    scores: dict  # FiveDimScores as dict
    is_self: bool
    scope: str  # "sedimentation" | "published"


@dataclass(frozen=True)
class UserSnapshot:
    """A user at the moment of extraction."""

    id: str
    reputation: dict | None  # ReputationScores as dict, or None


# ── Future snapshot types (used when signals come online) ──────────────────


@dataclass(frozen=True)
class FollowSnapshot:
    follower_id: str
    followed_id: str


@dataclass(frozen=True)
class ShareSnapshot:
    id: str
    sharer_id: str
    article_id: str
    recipient_id: str | None
    comment: str | None
    created_at: str  # ISO-8601


@dataclass(frozen=True)
class MergeProposalSnapshot:
    id: str
    fork_article_id: str
    target_article_id: str
    proposer_id: str
    status: str  # open | accepted | rejected | withdrawn


# ═══════════════════════════════════════════════════════════════════════════════
# State container
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ReputationState:
    """Complete input snapshot for reputation / prediction.

    Immutable.  Populated by ``extract_state()`` in commands/workflow.py.
    Add fields here as new signals come online.
    """

    articles: dict[str, ArticleSnapshot]
    reviews: dict[str, tuple[ReviewSnapshot, ...]]
    users: dict[str, UserSnapshot]

    # Future: populate as data pipelines come online
    follows: tuple[FollowSnapshot, ...] = ()
    shares: tuple[ShareSnapshot, ...] = ()
    merge_proposals: tuple[MergeProposalSnapshot, ...] = ()

    # ═══════════════════════════════════════════════════════════════════════
    # Serialization — dump as JSON for ML training data / debugging
    # ═══════════════════════════════════════════════════════════════════════

    def to_primitive(self) -> dict[str, Any]:
        """Recursively convert to plain dicts/lists — JSON-serializable."""
        return _to_primitive(self)


def _to_primitive(obj: Any) -> Any:
    """Recursively convert frozen dataclasses/tuples/dicts to plain types."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, tuple):
        return [_to_primitive(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_primitive(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {
            f.name: _to_primitive(getattr(obj, f.name))
            for f in fields(obj)
        }
    raise TypeError(f"Cannot serialize {type(obj).__name__}")
