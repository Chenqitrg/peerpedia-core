# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Pure-logic validation functions — zero DB, zero git, zero I/O.

Importable by both ``storage/db/guards.py`` and ``storage/db/crud_*.py``
without circular-dependency risk because this module imports nothing from
``storage/db/``.
"""

from __future__ import annotations

from typing import Any

from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.storage.db.models import ArticleMetaStorage, MergeProposalStorage


# ── Self-reference ─────────────────────────────────────────────────────────


def require_not_same(a: str, b: str, *, label: str) -> None:
    """Raise BadRequestError if *a* and *b* are the same."""
    if a == b:
        raise BadRequestError(f"Cannot {label} yourself")


# ── String validation ──────────────────────────────────────────────────────


def require_alias_nonempty(alias: str) -> None:
    """Raise ValueError if *alias* is empty or whitespace-only."""
    if not alias.strip():
        raise ValueError("Alias must not be empty")


def require_title_nonempty(title: str) -> None:
    """Raise BadRequestError if *title* is empty or whitespace-only."""
    if not title.strip():
        raise BadRequestError("Title is required")


# ── Numeric validation ─────────────────────────────────────────────────────


def require_helpfulness_score_range(score: int) -> None:
    """Raise BadRequestError if *score* is outside 1-5."""
    if score < 1 or score > 5:
        raise BadRequestError("Helpfulness score must be between 1 and 5")


# ── Crypto / key validation ────────────────────────────────────────────────


def require_signing_key(key_bytes: bytes | None, pubkey_hex: str | None, action: str) -> None:
    """Raise ValueError if signing key material is missing."""
    if key_bytes is None or not pubkey_hex:
        raise ValueError(f"signing_key_bytes and pubkey_hex are required for {action}")


# ── Entry / dict validation ────────────────────────────────────────────────


def require_keys(entries: list[dict[str, Any]], *keys: str, label: str) -> None:
    """Raise ValueError if any entry is missing a required key."""
    for e in entries:
        for k in keys:
            if not e.get(k):
                raise ValueError(f"ingest_{label}: missing '{k}' in entry {e}")


def validate_follow_entries(
    entries: list[dict[str, Any]], source_id: str, label: str,
) -> set[str]:
    """Validate follow entries and return the set of remote IDs."""
    require_keys(entries, "id", label=label)
    remote_ids = {e["id"] for e in entries}
    if source_id in remote_ids:
        raise ValueError(f"{label}: self-follow detected for user {source_id}")
    return remote_ids


# ── Object state ───────────────────────────────────────────────────────────


def require_draft_status(article: Article) -> None:
    """Raise BadRequestError if the article is not in draft status."""
    if article.status != "draft":
        raise BadRequestError("Only draft articles can be published")


def require_sedimentation(article: Article) -> None:
    """Raise BadRequestError if the article is not in sedimentation."""
    if article.status != "sedimentation":
        raise BadRequestError("Can only invite reviewers to articles in sedimentation")


def require_merge_proposal_open(mp: MergeProposal) -> None:
    """Raise BadRequestError if the merge proposal is not open."""
    if mp.status != "open":
        raise BadRequestError(f"Merge proposal {mp.id} is already {mp.status}")
