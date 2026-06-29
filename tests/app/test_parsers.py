# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Input parsers — parse_scores and parse_bootstrap_json."""

import json
import uuid

import pytest

from peerpedia_core.app.parsers import parse_bootstrap_json, parse_scores
from peerpedia_core.exceptions import BadRequestError


# ═══════════════════════════════════════════════════════════════════════════════
# parse_scores
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseScores:
    """Score string → {full_dimension_name: int} dict."""

    # ── Happy path ──────────────────────────────────────────────────────────

    def test_empty_string_returns_none(self):
        assert parse_scores("") is None

    def test_none_returns_none(self):
        assert parse_scores(None) is None

    def test_whitespace_only_returns_none(self):
        assert parse_scores("   ") is None

    def test_single_abbreviation(self):
        result = parse_scores("orig=4")
        assert result == {"originality": 4}

    def test_single_full_name(self):
        result = parse_scores("originality=4")
        assert result == {"originality": 4}

    def test_all_five_abbreviations(self):
        result = parse_scores("orig=4,rigor=3,comp=5,ped=2,imp=1")
        assert result == {
            "originality": 4,
            "rigor": 3,
            "completeness": 5,
            "pedagogy": 2,
            "impact": 1,
        }

    def test_all_five_full_names(self):
        result = parse_scores(
            "originality=4,rigor=3,completeness=5,pedagogy=2,impact=1"
        )
        assert result == {
            "originality": 4,
            "rigor": 3,
            "completeness": 5,
            "pedagogy": 2,
            "impact": 1,
        }

    def test_mixed_abbr_and_full(self):
        result = parse_scores("orig=4,rigor=3,completeness=5")
        assert result == {
            "originality": 4,
            "rigor": 3,
            "completeness": 5,
        }

    def test_handles_whitespace_around_commas(self):
        result = parse_scores("orig=4 , rigor=3 , comp=5")
        assert result == {
            "originality": 4,
            "rigor": 3,
            "completeness": 5,
        }

    def test_handles_whitespace_around_equals(self):
        result = parse_scores("orig = 4,rigor = 3")
        assert result == {
            "originality": 4,
            "rigor": 3,
        }

    def test_trailing_comma_is_fine(self):
        result = parse_scores("orig=4,")
        assert result == {"originality": 4}

    def test_boundary_score_1(self):
        result = parse_scores("orig=1")
        assert result == {"originality": 1}

    def test_boundary_score_5(self):
        result = parse_scores("orig=5")
        assert result == {"originality": 5}

    # ── Error: malformed ───────────────────────────────────────────────────

    def test_no_equals_sign_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_MALFORMED"):
            parse_scores("orig4")

    def test_equals_in_value_is_ok(self):
        """Only the first '=' is the split point."""
        # This is fine — split("=", 1) → ("orig", "4=2")
        # Then int("4=2") fails → SCORE_NOT_INT
        with pytest.raises(BadRequestError, match="SCORE_NOT_INT"):
            parse_scores("orig=4=2")

    # ── Error: unknown dimension ───────────────────────────────────────────

    def test_unknown_dimension_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_UNKNOWN_DIM"):
            parse_scores("beauty=4")

    def test_unknown_dimension_among_valid_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_UNKNOWN_DIM"):
            parse_scores("orig=4,beauty=4")

    # ── Error: not an integer ──────────────────────────────────────────────

    def test_non_integer_value_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_NOT_INT"):
            parse_scores("orig=good")

    def test_float_value_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_NOT_INT"):
            parse_scores("orig=4.5")

    def test_empty_value_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_NOT_INT"):
            parse_scores("orig=")

    # ── Error: out of range ────────────────────────────────────────────────

    def test_score_0_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_OUT_OF_RANGE"):
            parse_scores("orig=0")

    def test_score_6_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_OUT_OF_RANGE"):
            parse_scores("orig=6")

    def test_negative_score_raises(self):
        with pytest.raises(BadRequestError, match="SCORE_OUT_OF_RANGE"):
            parse_scores("orig=-1")


# ═══════════════════════════════════════════════════════════════════════════════
# parse_bootstrap_json
# ═══════════════════════════════════════════════════════════════════════════════

_VALID_UUID = str(uuid.uuid4())
_VALID_PUBKEY = "a" * 64  # 64-char hex
_VALID_SALT = "b" * 32    # 32-char hex


def _bootstrap_json(**overrides) -> str:
    """Build a valid bootstrap JSON string with optional field overrides."""
    data = {
        "name": "Alice",
        "user_id": _VALID_UUID,
        "public_key": _VALID_PUBKEY,
        "salt": _VALID_SALT,
    }
    data.update(overrides)
    return json.dumps(data)


class TestParseBootstrapJson:
    """Bootstrap JSON blob → validated dict."""

    # ── Happy path ──────────────────────────────────────────────────────────

    def test_valid_json_returns_dict(self):
        result = parse_bootstrap_json(
            _bootstrap_json()
        )
        assert result["name"] == "Alice"
        assert result["user_id"] == _VALID_UUID
        assert result["public_key"] == _VALID_PUBKEY
        assert result["salt"] == _VALID_SALT

    # ── Error: invalid JSON ────────────────────────────────────────────────

    def test_invalid_json_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_JSON"):
            parse_bootstrap_json("{not json}")

    def test_empty_string_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_JSON"):
            parse_bootstrap_json("")

    # ── Error: missing fields ──────────────────────────────────────────────

    @pytest.mark.parametrize("field", ["name", "user_id", "public_key", "salt"])
    def test_missing_field_raises(self, field):
        data = {
            "name": "Alice",
            "user_id": _VALID_UUID,
            "public_key": _VALID_PUBKEY,
            "salt": _VALID_SALT,
        }
        del data[field]
        with pytest.raises(BadRequestError, match="INVALID_BOOTSTRAP_FIELD"):
            parse_bootstrap_json(json.dumps(data))

    def test_empty_name_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_BOOTSTRAP_FIELD"):
            parse_bootstrap_json(_bootstrap_json(name=""))

    def test_empty_user_id_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_BOOTSTRAP_FIELD"):
            parse_bootstrap_json(_bootstrap_json(user_id=""))

    def test_empty_salt_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_BOOTSTRAP_FIELD"):
            parse_bootstrap_json(_bootstrap_json(salt=""))

    # ── Error: invalid UUID ────────────────────────────────────────────────

    def test_invalid_uuid_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_USER_ID"):
            parse_bootstrap_json(_bootstrap_json(user_id="not-a-uuid"))

    def test_uuid_is_required_field(self):
        """UUID must be a valid UUID string — not just any string."""
        with pytest.raises(BadRequestError, match="INVALID_USER_ID"):
            parse_bootstrap_json(_bootstrap_json(user_id="g" * 36))

    # ── Error: invalid pubkey ──────────────────────────────────────────────

    def test_pubkey_wrong_length_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_PUBKEY_LEN"):
            parse_bootstrap_json(_bootstrap_json(public_key="ab"))

    def test_pubkey_not_hex_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_PUBKEY"):
            parse_bootstrap_json(_bootstrap_json(public_key="z" * 64))

    def test_pubkey_empty_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_BOOTSTRAP_FIELD"):
            parse_bootstrap_json(_bootstrap_json(public_key=""))

    # ── Error: invalid salt ────────────────────────────────────────────────

    def test_salt_wrong_length_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_SALT_LEN"):
            parse_bootstrap_json(_bootstrap_json(salt="ab"))

    def test_salt_not_hex_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_SALT"):
            parse_bootstrap_json(_bootstrap_json(salt="z" * 32))

    def test_salt_empty_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_BOOTSTRAP_FIELD"):
            parse_bootstrap_json(_bootstrap_json(salt=""))
