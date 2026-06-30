# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Write operation authorization guards.

STATUS: LOCKED — these define product behavior for permission boundaries.
"""

import pytest

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError, NotFoundError

from tests.core.conftest import make_signing_key, make_user


# ── Helpers ──────────────────────────────────────────────────────────────────


def _article(db, author, *, title="Test", content="# X"):
    """Create a draft article owned by *author*."""
    from peerpedia_core.core import create_article_with_content

    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title=title, content=content,
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Permission boundaries — non-author guards
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonAuthorGuards:
    def test_non_author_cannot_edit(self, db, articles_dir):
        """User B cannot edit User A's article — authorship is immutable."""
        from peerpedia_core.core import update_article_content

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        a = _article(db, alice)

        with pytest.raises(NotAuthorizedError):
            update_article_content(
                db, a["id"], content="# Hacked",
                message="malicious edit", user_id=bob.id,
            )

    def test_non_author_cannot_delete(self, db, articles_dir):
        """User B cannot delete User A's article — only the author can."""
        from peerpedia_core.core import delete_article

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        a = _article(db, alice)

        with pytest.raises(NotAuthorizedError):
            delete_article(db, a["id"], user_id=bob.id)

    def test_non_author_cannot_publish(self, db, articles_dir):
        """User B cannot publish User A's draft — publish requires authorship."""
        from peerpedia_core.core import publish_article

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        bob_key, bob_pub = make_signing_key("bob@peerpedia")
        a = _article(db, alice)

        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}
        with pytest.raises(NotAuthorizedError):
            publish_article(
                db, a["id"], user_id=bob.id, self_review=scores,
                signing_key_bytes=bob_key, pubkey_hex=bob_pub,
            )

    def test_non_author_cannot_fork_draft(self, db, articles_dir):
        """Draft articles cannot be forked by non-authors —
        only published articles are openly forkable."""
        from peerpedia_core.core import fork_article

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        a = _article(db, alice)

        with pytest.raises(NotAuthorizedError):
            fork_article(db, a["id"], bob.id)


# ═══════════════════════════════════════════════════════════════════════════════
# Maintainer permission escalation guards
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaintainerGuards:
    def test_last_maintainer_cannot_be_removed(self, db, articles_dir):
        """The last maintainer of an article cannot remove themselves —
        every article must have at least one maintainer."""
        from peerpedia_core.core.maintainers import remove_maintainer_from_article
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        a = _article(db, alice)

        # Add Bob as maintainer, then remove Alice (the author)
        add_maintainer(db, a["id"], bob.id)
        db.flush()
        remove_maintainer_from_article(db, a["id"], alice.id, caller_id=alice.id)

        # Now Bob is the last maintainer — Bob cannot remove themself
        with pytest.raises(NotAuthorizedError):
            remove_maintainer_from_article(db, a["id"], bob.id, caller_id=bob.id)

    def test_non_maintainer_cannot_add_maintainer(self, db, articles_dir):
        """Only existing maintainers can add new maintainers —
        prevents unauthorized co-author injection."""
        from peerpedia_core.core.maintainers import add_maintainer_to_article

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        carol = make_user(db, "Carol")
        a = _article(db, alice)

        # Bob is NOT a maintainer — Bob should not be able to add Carol
        with pytest.raises(NotAuthorizedError):
            add_maintainer_to_article(db, a["id"], carol.id, caller_id=bob.id)

    def test_non_maintainer_cannot_accept_merge(self, db, articles_dir):
        """Only maintainers of the target article can accept merge proposals."""
        from peerpedia_core.core import create_article_with_content, fork_article
        from peerpedia_core.core.merge import create_merge_proposal, accept_merge
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = make_user(db, "Alice")
        forker = make_user(db, "Forker")
        outsider = make_user(db, "Outsider")
        key, pubkey = make_signing_key("alice@peerpedia")

        orig = create_article_with_content(
            db, title="Orig", content="# X",
            author_ids=[alice.id], signing_key_bytes=key, pubkey_hex=pubkey,
        )
        db.flush()
        add_maintainer(db, orig["id"], forker.id)
        db.flush()
        fork_result = fork_article(db, orig["id"], forker.id)

        mp = create_merge_proposal(db, fork_id=fork_result["id"],
                                   target_id=orig["id"], proposer_id=forker.id)

        # Outsider is not a maintainer — cannot accept merge
        with pytest.raises(NotAuthorizedError):
            accept_merge(db, orig["id"], mp.id, outsider.id)


# ═══════════════════════════════════════════════════════════════════════════════
# Status transition guards
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusTransitionGuards:
    def test_cannot_publish_already_published(self, db, articles_dir):
        """An already-published article cannot be published again —
        publication is a one-time transition (draft→sedimentation)."""
        from peerpedia_core.core import publish_article

        alice = make_user(db, "Alice")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        # First publish succeeds
        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)

        # Second publish on same article must fail
        with pytest.raises(BadRequestError):
            publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                            signing_key_bytes=key, pubkey_hex=pubkey)

    def test_cannot_delete_published_article(self, db, articles_dir):
        """Published articles cannot be deleted — only drafts can be removed."""
        from peerpedia_core.core import delete_article, publish_article

        alice = make_user(db, "Alice")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)

        with pytest.raises(NotAuthorizedError):
            delete_article(db, a["id"], user_id=alice.id)

    def test_publish_consents_cleared_after_publish(self, db, articles_dir):
        """Publish consents are cleared after publication —
        stale consents from future maintainers should not persist."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.maintainers import consent_to_publish
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        from peerpedia_core.storage.db.crud_article import get_article

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)

        add_maintainer(db, a["id"], bob.id)
        db.flush()

        # All maintainers must consent before publish
        consent_to_publish(db, a["id"], alice.id)
        consent_to_publish(db, a["id"], bob.id)

        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}
        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)

        article = get_article(db, a["id"])
        assert article.publish_consents is None or len(article.publish_consents) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Review state machine guards
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewStateMachineGuards:
    def test_cannot_accept_invitation_twice(self, db, articles_dir):
        """Accepting an already-accepted review invitation must fail —
        prevents double-acceptance of the same invitation."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import accept_invitation, invite_reviewer

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)
        invite_reviewer(db, a["id"], inviter_id=alice.id, invited_id=bob.id)
        accept_invitation(db, a["id"], bob.id)

        # After acceptance, the pending invitation row is gone — NotFoundError
        with pytest.raises(NotFoundError):
            accept_invitation(db, a["id"], bob.id)

    def test_cannot_decline_after_accept(self, db, articles_dir):
        """Declining after accepting must fail —
        once accepted, the reviewer is committed."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import accept_invitation, decline_invitation, invite_reviewer

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)
        invite_reviewer(db, a["id"], inviter_id=alice.id, invited_id=bob.id)
        accept_invitation(db, a["id"], bob.id)

        # Declining after acceptance is blocked by guard_invitation_not_accepted
        with pytest.raises(BadRequestError, match="INVITATION_ACCEPTED_ALREADY"):
            decline_invitation(db, a["id"], bob.id)

    def test_can_submit_review_on_sedimentation_without_invitation(self, db, articles_dir):
        """Anyone can submit a review on a sedimentation article —
        the invitation system solicits reviews but does not block unsolicited ones."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import submit_review

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        key, pubkey = make_signing_key("alice@peerpedia")
        bob_key, bob_pub = make_signing_key("bob@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)

        # Bob submits an unsolicited review — this is allowed
        long_comment = (
            "This paper presents an interesting approach to the problem. "
            "The methodology is sound and the results are clearly presented. "
            "However, there are several areas that could be improved including "
            "the literature review and the discussion section which needs work."
        )
        result = submit_review(
            db, a["id"], bob.id, scores,
            comment=long_comment,
            signing_key_bytes=bob_key, pubkey_hex=bob_pub,
        )
        assert result["review_id"] is not None

    def test_guard_invitation_conflicts_pending(self, db, articles_dir):
        """Inviting the same reviewer twice when an invitation is still pending
        raises INVITATION_PENDING — prevents duplicate pending invites."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import invite_reviewer

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)
        invite_reviewer(db, a["id"], inviter_id=alice.id, invited_id=bob.id)

        with pytest.raises(ConflictError, match="INVITATION_PENDING"):
            invite_reviewer(db, a["id"], inviter_id=alice.id, invited_id=bob.id)

    def test_guard_invitation_conflicts_accepted(self, db, articles_dir):
        """Inviting a reviewer who has already accepted their invitation
        raises INVITATION_ACCEPTED_ALREADY — prevents duplicate invite after accept."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import accept_invitation, invite_reviewer

        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob")
        key, pubkey = make_signing_key("alice@peerpedia")
        a = _article(db, alice)
        scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}

        publish_article(db, a["id"], user_id=alice.id, self_review=scores,
                        signing_key_bytes=key, pubkey_hex=pubkey)
        invite_reviewer(db, a["id"], inviter_id=alice.id, invited_id=bob.id)
        accept_invitation(db, a["id"], bob.id)

        with pytest.raises(ConflictError, match="INVITATION_ACCEPTED_ALREADY"):
            invite_reviewer(db, a["id"], inviter_id=alice.id, invited_id=bob.id)


# ═══════════════════════════════════════════════════════════════════════════════
# Closes: trailer guard — sedimentation edit integrity
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardClosesTrailer:
    def test_valid_closes_trailer_passes(self, db, articles_dir, tmp_path):
        """A commit message with a valid Closes: trailer referencing an existing
        thread file passes — sedimentation edits must cite review feedback."""
        from peerpedia_core.core.guards import guard_closes_trailer

        # Create the thread file and redirect the path that trailers.py uses
        import peerpedia_core.storage.git.trailers as trailers_mod
        orig = trailers_mod.DEFAULT_ARTICLES_DIR
        trailers_mod.DEFAULT_ARTICLES_DIR = tmp_path

        try:
            thread = tmp_path / "art-1" / "reviews" / "alice-review" / "threads" / "003.md"
            thread.parent.mkdir(parents=True)
            thread.write_text("# Thread 3")
            guard_closes_trailer("Closes: review/alice-review/thread-3", "art-1")
        finally:
            trailers_mod.DEFAULT_ARTICLES_DIR = orig

    def test_missing_closes_trailer_raises(self, db, articles_dir):
        """A commit message without a Closes: trailer raises
        MISSING_CLOSES_TRAILER — sedimentation edits require reviewer attribution."""
        from peerpedia_core.core.guards import guard_closes_trailer

        with pytest.raises(BadRequestError, match="MISSING_CLOSES_TRAILER"):
            guard_closes_trailer("Fixed typo", "art-1")

    def test_closes_target_not_found_raises(self, db, articles_dir):
        """A Closes: trailer referencing a non-existent thread raises
        CLOSES_TARGET_NOT_FOUND — the reference must be valid."""
        from peerpedia_core.core.guards import guard_closes_trailer

        with pytest.raises(BadRequestError, match="CLOSES_TARGET_NOT_FOUND"):
            guard_closes_trailer("Closes: review/nonexistent/thread-1", "art-1")

    def test_empty_commit_message_raises(self, db, articles_dir):
        """An empty commit message cannot have a Closes: trailer —
        raises MISSING_CLOSES_TRAILER."""
        from peerpedia_core.core.guards import guard_closes_trailer

        with pytest.raises(BadRequestError, match="MISSING_CLOSES_TRAILER"):
            guard_closes_trailer("", "art-1")
