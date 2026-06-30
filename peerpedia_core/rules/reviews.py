# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Pure review validation rules — zero IO, zero DB/git dependencies."""

from __future__ import annotations

from peerpedia_core.config.params import params
from peerpedia_core.exceptions import BadRequestError, NotAuthorizedError
from peerpedia_core.types.scores import SCORE_DIMENSIONS, normalize_score_keys


def assert_valid_review(scores: dict, comment: str | None = None, *, check_comment: bool = True) -> None:
    """Validate a review before submission — shared by local and sync paths.

    Raises BadRequestError if scores are invalid or comment is too short.
    """
    # ── Validate ───────────────────────────────────────────────────────────
    errors = _collect_review_errors(scores, comment, check_comment=check_comment)
    if errors:
        raise BadRequestError(code="INVALID_REVIEW")

    # ── Normalize keys ─────────────────────────────────────────────────────
    normalize_score_keys(scores)


def _collect_review_errors(scores: dict, comment: str | None, *, check_comment: bool) -> list[str]:
    """Orchestrate review validation — delegate to individual checkers."""
    errors: list[str] = []

    if check_comment:
        _validate_review_comment(comment, errors)
    _validate_review_scores(scores, errors)

    return errors


def _validate_review_scores(scores: dict, errors: list[str]) -> None:
    """Append score validation errors to *errors* list."""
    if not isinstance(scores, dict):
        errors.append("scores must be a dict")
        return

    _check_score_dimensions(scores, errors)
    _check_score_values(scores, errors)


def _check_score_dimensions(scores: dict, errors: list[str]) -> None:
    """Append dimension completeness errors to *errors* list."""
    abbr_dims = set(SCORE_DIMENSIONS.keys())
    full_dims = set(SCORE_DIMENSIONS.values())
    keys = set(scores.keys())
    if not (abbr_dims.issubset(keys) or full_dims.issubset(keys)):
        errors.append(
            f"scores must contain all {len(SCORE_DIMENSIONS)} dimensions: "
            f"{', '.join(sorted(SCORE_DIMENSIONS.keys()))}"
        )


def _check_score_values(scores: dict, errors: list[str]) -> None:
    """Append score value range errors (1-5) to *errors* list."""
    for dim, val in scores.items():
        if not isinstance(val, (int, float)) or val < 1 or val > 5:
            errors.append(
                f"score dimension '{dim}' must be a number between 1 and 5, got {val!r}"
            )


def _validate_review_comment(comment: str | None, errors: list[str]) -> None:
    """Append comment validation errors to *errors* list."""

    min_len = params.comment.min_length
    if not comment or not isinstance(comment, str):
        errors.append("Review comment is required")
    elif len(comment.strip()) < min_len:
        actual = len(comment.strip())
        errors.append(
            f"Review comment must be at least {min_len} characters "
            f"(got {actual} — {min_len - actual} more needed). "
            f"Tip: echo 'your comment' | wc -c to count before pasting."
        )


# ── Pure utility guards ──────────────────────────────────────────────────────


def guard_proposal_owner(mp, user_id: str) -> None:
    """Raise NotAuthorizedError if *user_id* is not the proposal owner."""
    if mp.proposer_id != user_id:
        raise NotAuthorizedError(code="NOT_PROPOSAL_CREATOR")


def require_signing_key_not_none(signing_key: bytes | None) -> None:
    """Raise BadRequestError if *signing_key* is None."""
    if signing_key is None:
        raise BadRequestError(code="MISSING_SIGNING_KEY")


def require_integrity_level(level: str) -> None:
    """Raise ValueError if *level* is not 'light' or 'full'."""
    if level not in ("light", "full"):
        raise ValueError(f"INVALID_INTEGRITY_LEVEL: {level}")
