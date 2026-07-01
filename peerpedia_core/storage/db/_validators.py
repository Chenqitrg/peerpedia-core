# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Pure-logic validation functions — zero DB, zero git, zero I/O.

Importable by both ``storage/db/guards.py`` and the CRUD modules
without circular-dependency risk because this module imports nothing from
``storage/db/``.
"""

from __future__ import annotations

from typing import Any

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db.models import ArticleMetaStorage, MergeProposalStorage
from peerpedia_core.types.status import ArticleStatus


# ── Self-reference ─────────────────────────────────────────────────────────


def require_not_same(a: str, b: str, *, label: str) -> None:
    """Raise BadRequestError if *a* and *b* are the same."""
    if a == b:
        raise BadRequestError(code="CANNOT_SELF_ACTION")


# ── String validation ──────────────────────────────────────────────────────


def require_alias_nonempty(alias: str) -> None:
    """Raise ValueError if *alias* is empty or whitespace-only."""
    if not alias.strip():
        raise ValueError("ALIAS_EMPTY")


def require_title_nonempty(title: str) -> None:
    """Raise BadRequestError if *title* is empty or whitespace-only."""
    if not title.strip():
        raise BadRequestError(code="TITLE_REQUIRED")


# ── Numeric validation ─────────────────────────────────────────────────────


def require_helpfulness_score_range(score: int) -> None:
    """Raise BadRequestError if *score* is outside 1-5."""
    if score < 1 or score > 5:
        raise BadRequestError(code="HELPFULNESS_RANGE")


# ── Crypto / key validation ────────────────────────────────────────────────


def require_signing_key(key_bytes: bytes | None, pubkey_hex: str | None, action: str) -> None:
    """Raise BadRequestError if signing key material is missing."""
    if key_bytes is None or not pubkey_hex:
        raise BadRequestError(code="MISSING_SIGNING_KEY")


# ── Entry / dict validation ────────────────────────────────────────────────


def require_keys(entries: list[dict[str, object]], *keys: str, label: str) -> None:
    """Raise BadRequestError if any entry is missing a required key."""
    for e in entries:
        for k in keys:
            if not e.get(k):
                raise BadRequestError(code="VALIDATION_FAILED")


def validate_follow_entries(
    entries: list[dict[str, object]], source_id: str, label: str,
) -> set[str]:
    """Validate follow entries and return the set of remote IDs."""
    require_keys(entries, "id", label=label)
    remote_ids = {e["id"] for e in entries}
    if source_id in remote_ids:
        raise BadRequestError(code="SELF_FOLLOW")
    return remote_ids


# ── Object state ───────────────────────────────────────────────────────────


def require_draft_status(article: ArticleMetaStorage) -> None:
    """Raise BadRequestError if the article is not in draft status."""
    if article.status != ArticleStatus.DRAFT:
        raise BadRequestError(code="VALIDATION_FAILED")


def require_sedimentation(article: ArticleMetaStorage) -> None:
    """Raise BadRequestError if the article is not in sedimentation."""
    if article.status != ArticleStatus.SEDIMENTATION:
        raise BadRequestError(code="SEDIMENTATION_INVITE_ONLY")


def require_merge_proposal_open(mp: MergeProposalStorage) -> None:
    """Raise BadRequestError if the merge proposal is not open."""
    if mp.status != "open":
        raise BadRequestError(code="MERGE_PROPOSAL_CLOSED")
