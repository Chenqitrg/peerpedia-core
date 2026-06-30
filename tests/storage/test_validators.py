# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/db/_validators.py — pure validation functions."""

import pytest

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db._validators import (
    require_alias_nonempty,
    require_draft_status,
    require_helpfulness_score_range,
    require_keys,
    require_merge_proposal_open,
    require_not_same,
    require_sedimentation,
    require_signing_key,
    require_title_nonempty,
    validate_follow_entries,
)
from peerpedia_core.storage.db.models import ArticleMetaStorage, MergeProposalStorage


# ── Helpers ──────────────────────────────────────────────────────────────────


def _article(status: str) -> ArticleMetaStorage:
    """Minimal ArticleMetaStorage with just the .status attribute set."""
    a = ArticleMetaStorage()
    a.status = status
    return a


def _merge_proposal(status: str) -> MergeProposalStorage:
    """Minimal MergeProposalStorage with just the .status attribute set."""
    mp = MergeProposalStorage()
    mp.status = status
    return mp


# ═══════════════════════════════════════════════════════════════════════════════
# require_not_same
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireNotSame:
    def test_different_values_ok(self):
        """Two different strings pass — guards against self-targeting actions."""
        require_not_same("alice", "bob", label="follow")  # should not raise

    def test_same_values_raises(self):
        """Identical strings raise CANNOT_SELF_ACTION — prevents self-follow etc."""
        with pytest.raises(BadRequestError, match="CANNOT_SELF_ACTION"):
            require_not_same("alice", "alice", label="follow")


# ═══════════════════════════════════════════════════════════════════════════════
# require_alias_nonempty
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireAliasNonempty:
    def test_nonempty_alias_ok(self):
        """A valid alias is not rejected."""
        require_alias_nonempty("my-friend")  # should not raise

    def test_empty_alias_raises(self):
        """Empty alias raises ALIAS_EMPTY — prevents nameless aliases."""
        with pytest.raises(ValueError, match="ALIAS_EMPTY"):
            require_alias_nonempty("")

    def test_whitespace_alias_raises(self):
        """Whitespace-only alias is treated as empty."""
        with pytest.raises(ValueError, match="ALIAS_EMPTY"):
            require_alias_nonempty("   ")


# ═══════════════════════════════════════════════════════════════════════════════
# require_title_nonempty
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireTitleNonempty:
    def test_nonempty_title_ok(self):
        """A valid title passes validation."""
        require_title_nonempty("My Research Paper")  # should not raise

    def test_empty_title_raises(self):
        """Empty title raises TITLE_REQUIRED — articles must have a title."""
        with pytest.raises(BadRequestError, match="TITLE_REQUIRED"):
            require_title_nonempty("")


# ═══════════════════════════════════════════════════════════════════════════════
# require_helpfulness_score_range
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireHelpfulnessScoreRange:
    def test_score_1_ok(self):
        """Score 1 (minimum) passes."""
        require_helpfulness_score_range(1)  # should not raise

    def test_score_5_ok(self):
        """Score 5 (maximum) passes."""
        require_helpfulness_score_range(5)  # should not raise

    def test_score_0_raises(self):
        """Score 0 is below the valid range — raises HELPFULNESS_RANGE."""
        with pytest.raises(BadRequestError, match="HELPFULNESS_RANGE"):
            require_helpfulness_score_range(0)

    def test_score_6_raises(self):
        """Score 6 is above the valid range — raises HELPFULNESS_RANGE."""
        with pytest.raises(BadRequestError, match="HELPFULNESS_RANGE"):
            require_helpfulness_score_range(6)

    def test_negative_score_raises(self):
        """Negative scores are rejected — only 1-5 are valid helpfulness ratings."""
        with pytest.raises(BadRequestError, match="HELPFULNESS_RANGE"):
            require_helpfulness_score_range(-1)


# ═══════════════════════════════════════════════════════════════════════════════
# require_signing_key
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireSigningKey:
    def test_both_present_ok(self):
        """Both key_bytes and pubkey_hex provided — signing is possible."""
        require_signing_key(b"deadbeef", "abc123", "commit")  # should not raise

    def test_key_bytes_none_raises(self):
        """Missing private key bytes raises MISSING_SIGNING_KEY."""
        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_signing_key(None, "abc123", "commit")

    def test_pubkey_empty_raises(self):
        """Empty pubkey hex raises MISSING_SIGNING_KEY — no identity to verify."""
        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_signing_key(b"deadbeef", "", "commit")

    def test_pubkey_none_raises(self):
        """None pubkey hex raises MISSING_SIGNING_KEY."""
        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_signing_key(b"deadbeef", None, "commit")

    def test_both_missing_raises(self):
        """Neither key nor pubkey provided — cannot sign at all."""
        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_signing_key(None, "", "commit")


# ═══════════════════════════════════════════════════════════════════════════════
# require_keys
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireKeys:
    def test_all_keys_present_ok(self):
        """Every entry has every required key."""
        entries = [{"id": "a", "name": "Alice"}, {"id": "b", "name": "Bob"}]
        require_keys(entries, "id", "name", label="test")  # should not raise

    def test_missing_key_raises(self):
        """An entry missing a required key raises VALIDATION_FAILED."""
        entries = [{"id": "a"}, {"id": "b", "name": None}]  # name is None → falsy → fail
        with pytest.raises(BadRequestError, match="VALIDATION_FAILED"):
            require_keys(entries, "id", "name", label="test")

    def test_empty_value_treated_as_missing(self):
        """Empty string value is treated as missing — falsy check in guard."""
        entries = [{"id": "a", "name": ""}]
        with pytest.raises(BadRequestError, match="VALIDATION_FAILED"):
            require_keys(entries, "id", "name", label="test")


# ═══════════════════════════════════════════════════════════════════════════════
# validate_follow_entries
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateFollowEntries:
    def test_extracts_remote_ids(self):
        """Returns the set of remote IDs from valid follow entries."""
        entries = [{"id": "bob"}, {"id": "carol"}]
        result = validate_follow_entries(entries, "alice", "follow")
        assert result == {"bob", "carol"}

    def test_self_follow_raises(self):
        """source_id in the follow list raises SELF_FOLLOW — can't follow yourself."""
        entries = [{"id": "alice"}, {"id": "bob"}]
        with pytest.raises(BadRequestError, match="SELF_FOLLOW"):
            validate_follow_entries(entries, "alice", "follow")


# ═══════════════════════════════════════════════════════════════════════════════
# require_draft_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireDraftStatus:
    def test_draft_ok(self):
        """Article in 'draft' status passes — editing is allowed."""
        require_draft_status(_article("draft"))  # should not raise

    def test_published_raises(self):
        """Published article cannot be treated as draft — raises VALIDATION_FAILED."""
        with pytest.raises(BadRequestError, match="VALIDATION_FAILED"):
            require_draft_status(_article("published"))


# ═══════════════════════════════════════════════════════════════════════════════
# require_sedimentation
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireSedimentation:
    def test_sedimentation_ok(self):
        """Article in 'sedimentation' status passes — review invitation allowed."""
        require_sedimentation(_article("sedimentation"))  # should not raise

    def test_draft_raises(self):
        """Draft article cannot receive review invites — raises SEDIMENTATION_INVITE_ONLY."""
        with pytest.raises(BadRequestError, match="SEDIMENTATION_INVITE_ONLY"):
            require_sedimentation(_article("draft"))


# ═══════════════════════════════════════════════════════════════════════════════
# require_merge_proposal_open
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireMergeProposalOpen:
    def test_open_ok(self):
        """Merge proposal in 'open' status passes — actions allowed."""
        require_merge_proposal_open(_merge_proposal("open"))  # should not raise

    def test_accepted_raises(self):
        """Already-accepted merge proposal raises MERGE_PROPOSAL_CLOSED."""
        with pytest.raises(BadRequestError, match="MERGE_PROPOSAL_CLOSED"):
            require_merge_proposal_open(_merge_proposal("accepted"))
