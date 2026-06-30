# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Review thread — submit replies, write reviews to git, anonymous identity.

STATUS: LOCKED — these define product behavior for review thread interactions.
"""

from pathlib import Path

import pytest

from tests.core.conftest import make_signing_key, make_user


def _article(db, author, *, title="Test", content="# X"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title=title, content=content,
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


def _scores(orig=4, rig=4, comp=4, ped=4, imp=4):
    return {"originality": orig, "rigor": rig, "completeness": comp, "pedagogy": ped, "impact": imp}


# ═══════════════════════════════════════════════════════════════════════════════
# submit_reply — author replies to review threads
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubmitReply:
    def test_author_can_reply_to_review(self, db, articles_dir):
        """An article author can submit a reply to a review thread —
        reply is written to git and returns article_id, directory_id, commit_hash."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews.thread import submit_reply

        author = make_user(db, "Author")
        reviewer = make_user(db, "Reviewer")  # must be a real user for reviewer_ref
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        # Publish to get into sedimentation (needed for replies)
        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        result = submit_reply(
            db, a["id"], author.id, reviewer.id,
            content="Thank you for the detailed feedback. We have addressed your concerns.",
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        assert result["article_id"] == a["id"]
        assert result["directory_id"] is not None
        assert len(result["commit_hash"]) == 40

    def test_non_author_cannot_reply(self, db, articles_dir):
        """Non-authors cannot reply to reviews — only maintainers can respond."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews.thread import submit_reply

        author = make_user(db, "Author")
        outsider = make_user(db, "Outsider")
        reviewer = make_user(db, "Reviewer")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")
        outsider_key, outsider_pub = make_signing_key("outsider@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        with pytest.raises(Exception):
            submit_reply(
                db, a["id"], outsider.id, reviewer.id,
                content="Unsolicited reply that should not be accepted by the system.",
                signing_key_bytes=outsider_key, pubkey_hex=outsider_pub,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# write_review_to_git — scores + thread files in git
# ═══════════════════════════════════════════════════════════════════════════════


class TestWriteReviewToGit:
    def test_creates_scores_and_thread_files(self, db, articles_dir):
        """Writing a review to git creates scores.json and a thread .md file
        in the correct review directory structure."""
        from peerpedia_core.core.reviews.thread import write_review_to_git
        from peerpedia_core.config.paths import article_repo_path

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        commit_hash = write_review_to_git(
            a["id"], "test-reviewer", _scores(),
            comment="Thorough and rigorous work with clear methodology and results.",
            display_name="Test Reviewer", email="reviewer@peerpedia",
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        assert len(commit_hash) == 40

        rp = article_repo_path(a["id"])
        scores_file = rp / "reviews" / "test-reviewer" / "scores.json"
        assert scores_file.is_file()
        thread_files = list((rp / "reviews" / "test-reviewer" / "threads").glob("*.md"))
        assert len(thread_files) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Anonymous identity — HMAC-derived directory IDs for sedimentation
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnonymousIdentity:
    def test_derive_anonymous_id_deterministic(self, db, articles_dir):
        """The same (article_id, signing_key) always produces the same anonymous
        directory ID — enables reviewer pseudonymity with stable identity."""
        from peerpedia_core.core.reviews.thread import _derive_anonymous_id

        key1, _ = make_signing_key("reviewer@peerpedia")
        id1 = _derive_anonymous_id("art-1", signing_key=key1)
        id2 = _derive_anonymous_id("art-1", signing_key=key1)
        assert id1 == id2

    def test_derive_anonymous_id_different_per_article(self, db, articles_dir):
        """Same reviewer gets different anonymous IDs for different articles —
        cross-article pseudonymity is maintained."""
        from peerpedia_core.core.reviews.thread import _derive_anonymous_id

        key1, _ = make_signing_key("reviewer@peerpedia")
        id_a = _derive_anonymous_id("art-a", signing_key=key1)
        id_b = _derive_anonymous_id("art-b", signing_key=key1)
        assert id_a != id_b

    def test_derive_anonymous_id_different_per_reviewer(self, db, articles_dir):
        """Different reviewers get different anonymous IDs for the same article —
        reviewer identity is distinguishable within a paper."""
        from peerpedia_core.core.reviews.thread import _derive_anonymous_id

        key1, _ = make_signing_key("reviewer-a@peerpedia")
        key2, _ = make_signing_key("reviewer-b@peerpedia")
        id_a = _derive_anonymous_id("art-1", signing_key=key1)
        id_b = _derive_anonymous_id("art-1", signing_key=key2)
        assert id_a != id_b
