# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Input parsers — convert CLI/REPL string arguments into typed values.

Reusable by CLI, REPL, and server.  Raises ``ValidationFailed`` on
malformed input — never calls ``_out()`` or ``sys.exit()``.
"""

from __future__ import annotations

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.types.scores import SCORE_DIMENSIONS


def parse_scores(scores_str: str | None) -> dict[str, int] | None:
    """Parse ``"orig=4,rigor=3,..."`` into a ``{full_name: int}`` dict.

    Validates dimension names (abbreviation or full) and 1–5 range.
    Returns ``None`` for empty input.  Raises ``ValidationFailed`` on
    invalid input.
    """
    if not scores_str:
        return None

    valid_abbr = set(SCORE_DIMENSIONS.keys())
    valid_full = set(SCORE_DIMENSIONS.values())
    valid = valid_abbr | valid_full

    result: dict[str, int] = {}
    for part in scores_str.split(","):
        part = part.strip()
        if not part:
            continue
        k, v = _parse_score_part(part, valid, valid_abbr)
        result[k] = v
    return result


def _parse_score_part(
    part: str,
    valid_keys: set[str],
    valid_abbr: set[str],
) -> tuple[str, int]:
    """Parse one ``key=value`` score part.  Raises ``ValidationFailed``."""
    if "=" not in part:
        raise BadRequestError(code="SCORE_MALFORMED", part=part)
    k, v = part.split("=", 1)
    k, v = k.strip(), v.strip()

    if k not in valid_keys:
        abbr_list = ", ".join(sorted(valid_abbr))
        raise BadRequestError(code="SCORE_UNKNOWN_DIM", key=k, valid=abbr_list)

    # Normalize abbreviations to full names (downstream code expects full names).
    if k in valid_abbr:
        k = SCORE_DIMENSIONS[k]

    try:
        score = int(v)
    except ValueError:
        raise BadRequestError(code="SCORE_NOT_INT", key=k, value=v)

    if not 1 <= score <= 5:
        raise BadRequestError(code="SCORE_OUT_OF_RANGE", key=k, value=str(score))

    return k, score


def parse_bootstrap_json(json_str: str) -> dict:
    """Parse and validate a bootstrap JSON blob.  Raises ``ValidationFailed``."""
    import json as _json
    import uuid as _uuid
    try:
        data = _json.loads(json_str)
    except _json.JSONDecodeError as e:
        raise BadRequestError(code="INVALID_JSON", error=str(e))
    for field in ("name", "user_id", "public_key", "salt"):
        if not data.get(field):
            raise BadRequestError(code="INVALID_BOOTSTRAP_FIELD", field=field)
    try:
        _uuid.UUID(data["user_id"])
    except (ValueError, AttributeError):
        raise BadRequestError(code="INVALID_USER_ID", value=str(data["user_id"]))
    if len(data["public_key"]) != 64:
        raise BadRequestError(code="INVALID_PUBKEY_LEN", length=len(data["public_key"]))
    if len(data["salt"]) != 32:
        raise BadRequestError(code="INVALID_SALT_LEN", length=len(data["salt"]))
    try:
        bytes.fromhex(data["public_key"])
    except (ValueError, AttributeError):
        raise BadRequestError(code="INVALID_PUBKEY")
    try:
        bytes.fromhex(data["salt"])
    except (ValueError, AttributeError):
        raise BadRequestError(code="INVALID_SALT")
    return data
