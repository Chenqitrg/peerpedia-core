# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for DB-layer guard functions — fail-fast, reference message codes."""

import uuid

import pytest

from peerpedia_core.config.params import params
from peerpedia_core.exceptions import (
    BadRequestError, ConflictError, NotFoundError, NotAuthorizedError,
)
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.guards import (
    assert_caller_is_maintainer,
    authorize_article_action,
    guard_not_already_maintainer,
    guard_not_last_maintainer,
    guard_invitation_not_accepted,
    guard_invitation_not_declined,
    guard_sedimentation_limit,
    require_article,
    require_authors_exist,
    require_following_for_alias,
    require_invitation,
    require_maintainer,
    require_open_proposal,
    require_review,
    require_user,
)
from peerpedia_core.storage.db.models import (
    ArticleMetaStorage, MergeProposalStorage, ReviewMetaStorage, UserStorage,
)
from tests.crud.conftest import default_scores, make_article, make_user

_PK = "0000000000000000000000000000000000000000000000000000000000000000"


def _make_maintainer(session, article_id, user_id):
    from peerpedia_core.storage.db.models import ScriptMaintainerStorage
    session.add(ScriptMaintainerStorage(article_id=article_id, user_id=user_id))
    session.flush()


def _make_review(session, article_id, reviewer_id, *, status="submitted", scores=None):
    r = ReviewMetaStorage(
        id=str(uuid.uuid4()),
        article_id=article_id,
        commit_hash=str(uuid.uuid4())[:8],
        reviewer_id=reviewer_id,
        scope="sedimentation",
        status=status,
        scores=scores or default_scores(),
    )
    session.add(r)
    session.flush()
    return r


def _make_merge_proposal(session, fork_id, target_id, proposer_id, *, closed=False):
    from peerpedia_core.storage.db.crud_merge import create_merge_proposal, accept_merge_proposal
    mp = create_merge_proposal(session, fork_id=fork_id, target_id=target_id, proposer_id=proposer_id)
    if closed:
        accept_merge_proposal(session, mp.id)
    return mp


# ═══════════════════════════════════════════════════════════════════════════════
# require_user / require_article
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireExists:
    def test_require_user_found(self, engine):
        session = get_session(engine)
        u = make_user(session, "alice")
        assert require_user(session, u.id).name == "alice"
        session.close()

    def test_require_user_not_found(self, engine):
        session = get_session(engine)
        with pytest.raises(NotFoundError, match="USER_NOT_FOUND"):
            require_user(session, "nonexistent")
        session.close()

    def test_require_article_found(self, engine):
        session = get_session(engine)
        u = make_user(session, "author")
        a = make_article(session, authors=[u.id])
        assert require_article(session, a.id).title is not None
        session.close()

    def test_require_article_not_found(self, engine):
        session = get_session(engine)
        with pytest.raises(NotFoundError, match="ARTICLE_NOT_FOUND"):
            require_article(session, "nonexistent")
        session.close()

    def test_require_authors_exist_all_found(self, engine):
        session = get_session(engine)
        u1 = make_user(session, "a1")
        u2 = make_user(session, "a2")
        require_authors_exist(session, [u1.id, u2.id])  # should not raise
        session.close()

    def test_require_authors_exist_any_missing(self, engine):
        session = get_session(engine)
        u = make_user(session, "exists")
        with pytest.raises(NotFoundError, match="USER_NOT_FOUND"):
            require_authors_exist(session, [u.id, "nonexistent"])
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# require_maintainer / assert_caller_is_maintainer
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaintainerGuards:
    def test_require_maintainer_is_maintainer(self, engine):
        session = get_session(engine)
        u = make_user(session, "owner")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        require_maintainer(session, a.id, u.id)  # should not raise
        session.close()

    def test_require_maintainer_not_maintainer(self, engine):
        session = get_session(engine)
        u = make_user(session, "owner")
        stranger = make_user(session, "stranger")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        with pytest.raises(NotAuthorizedError, match="NOT_MAINTAINER"):
            require_maintainer(session, a.id, stranger.id)
        session.close()

    def test_assert_caller_is_maintainer_success(self, engine):
        session = get_session(engine)
        u = make_user(session, "owner")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        assert_caller_is_maintainer(session, a.id, u.id)
        session.close()

    def test_assert_caller_is_maintainer_user_not_found(self, engine):
        session = get_session(engine)
        a = make_article(session, authors=[make_user(session, "author").id])
        with pytest.raises(NotFoundError, match="USER_NOT_FOUND"):
            assert_caller_is_maintainer(session, a.id, "nonexistent")
        session.close()

    def test_assert_caller_is_maintainer_article_not_found(self, engine):
        session = get_session(engine)
        u = make_user(session, "caller")
        with pytest.raises(NotFoundError, match="ARTICLE_NOT_FOUND"):
            assert_caller_is_maintainer(session, "nonexistent", u.id)
        session.close()

    def test_assert_not_maintainer_raises(self, engine):
        session = get_session(engine)
        u = make_user(session, "owner")
        stranger = make_user(session, "stranger")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        with pytest.raises(NotAuthorizedError, match="NOT_MAINTAINER"):
            assert_caller_is_maintainer(session, a.id, stranger.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# guard_not_already_maintainer
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardNotAlreadyMaintainer:
    def test_not_maintainer_ok(self, engine):
        session = get_session(engine)
        u = make_user(session, "owner")
        new = make_user(session, "new")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        guard_not_already_maintainer(session, a.id, new.id)  # should not raise
        session.close()

    def test_already_maintainer_raises(self, engine):
        session = get_session(engine)
        u = make_user(session, "owner")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        with pytest.raises(ConflictError, match="ALREADY_MAINTAINER"):
            guard_not_already_maintainer(session, a.id, u.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# guard_sedimentation_limit
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardSedimentationLimit:
    def test_under_limit_ok(self, engine):
        session = get_session(engine)
        u = make_user(session, "author")
        # One article in sedimentation — under the max of 5
        make_article(session, authors=[u.id], status="sedimentation")
        guard_sedimentation_limit(session, u.id)  # should not raise
        session.close()

    def test_at_limit_raises(self, engine):
        session = get_session(engine)
        u = make_user(session, "author")
        for _ in range(params.sink.max_sedimentation_per_author):
            make_article(session, authors=[u.id], status="sedimentation")
        with pytest.raises(BadRequestError, match="SEDIMENTATION_LIMIT"):
            guard_sedimentation_limit(session, u.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# guard_not_last_maintainer
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardNotLastMaintainer:
    def test_multiple_maintainers_ok(self, engine):
        session = get_session(engine)
        u1 = make_user(session, "m1")
        u2 = make_user(session, "m2")
        a = make_article(session, authors=[u1.id])
        _make_maintainer(session, a.id, u1.id)
        _make_maintainer(session, a.id, u2.id)
        guard_not_last_maintainer(session, a.id, u1.id, u1.id)  # self-remove OK: 2 left
        session.close()

    def test_removing_other_maintainer_ok(self, engine):
        """Removing someone else is always OK, even if only one maintainer."""
        session = get_session(engine)
        u1 = make_user(session, "m1")
        u2 = make_user(session, "m2")
        a = make_article(session, authors=[u1.id])
        _make_maintainer(session, a.id, u1.id)
        guard_not_last_maintainer(session, a.id, u1.id, u2.id)  # u1 removes u2, u1 stays
        session.close()

    def test_last_maintainer_self_remove_raises(self, engine):
        session = get_session(engine)
        u = make_user(session, "sole")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        with pytest.raises(NotAuthorizedError, match="LAST_MAINTAINER"):
            guard_not_last_maintainer(session, a.id, u.id, u.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# require_following_for_alias
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireFollowingForAlias:
    def test_follows_ok(self, engine):
        from peerpedia_core.storage.db.crud_follow import follow_user
        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        follow_user(session, alice.id, bob.id)
        require_following_for_alias(session, alice.id, bob.id)  # should not raise
        session.close()

    def test_not_following_raises(self, engine):
        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        with pytest.raises(BadRequestError, match="MUST_FOLLOW_FOR_ALIAS"):
            require_following_for_alias(session, alice.id, bob.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# require_review
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireReview:
    def test_review_found(self, engine):
        session = get_session(engine)
        u = make_user(session, "author")
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[u.id], status="sedimentation")
        _make_review(session, a.id, rv.id)
        found = require_review(session, a.id, rv.id)
        assert found.reviewer_id == rv.id
        session.close()

    def test_review_not_found(self, engine):
        session = get_session(engine)
        u = make_user(session, "author")
        a = make_article(session, authors=[u.id], status="sedimentation")
        with pytest.raises(NotFoundError, match="REVIEW_NOT_FOUND"):
            require_review(session, a.id, "nonexistent")
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# require_open_proposal
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireOpenProposal:
    def test_open_proposal_ok(self, engine):
        session = get_session(engine)
        author = make_user(session, "author")
        forker = make_user(session, "forker")
        original = make_article(session, authors=[author.id])
        fork = make_article(session, authors=[forker.id])
        mp = _make_merge_proposal(session, fork.id, original.id, forker.id)
        result = require_open_proposal(session, mp.id, original.id)
        assert result.status == "open"
        session.close()

    def test_proposal_not_found(self, engine):
        session = get_session(engine)
        with pytest.raises(NotFoundError, match="MERGE_PROPOSAL_NOT_FOUND"):
            require_open_proposal(session, "nonexistent", "nonexistent")
        session.close()

    def test_wrong_article(self, engine):
        session = get_session(engine)
        author = make_user(session, "author")
        forker = make_user(session, "forker")
        a1 = make_article(session, authors=[author.id])
        a2 = make_article(session, authors=[author.id])
        fork = make_article(session, authors=[forker.id])
        mp = _make_merge_proposal(session, fork.id, a1.id, forker.id)
        with pytest.raises(BadRequestError, match="MERGE_PROPOSAL_WRONG_ARTICLE"):
            require_open_proposal(session, mp.id, a2.id)
        session.close()

    def test_proposal_closed(self, engine):
        session = get_session(engine)
        author = make_user(session, "author")
        forker = make_user(session, "forker")
        original = make_article(session, authors=[author.id])
        fork = make_article(session, authors=[forker.id])
        mp = _make_merge_proposal(session, fork.id, original.id, forker.id, closed=True)
        with pytest.raises(BadRequestError, match="MERGE_PROPOSAL_CLOSED"):
            require_open_proposal(session, mp.id, original.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Review invitation guards
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvitationGuards:
    def test_require_invitation_accepted_ok(self, engine):
        from peerpedia_core.core.reviews.invite import invite_reviewer, accept_invitation
        session = get_session(engine)
        inviter = make_user(session, "inviter")
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[make_user(session, "author").id], status="sedimentation")
        _make_maintainer(session, a.id, inviter.id)
        invite_reviewer(session, article_id=a.id, inviter_id=inviter.id, invited_id=rv.id)
        accept_invitation(session, a.id, rv.id)
        require_invitation(session, a.id, rv.id)  # should not raise
        session.close()

    def test_require_invitation_no_invitation_raises(self, engine):
        session = get_session(engine)
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[make_user(session, "author").id], status="sedimentation")
        with pytest.raises(NotAuthorizedError, match="NO_INVITATION"):
            require_invitation(session, a.id, rv.id)
        session.close()

    def test_guard_invitation_not_declined_ok(self, engine):
        session = get_session(engine)
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[make_user(session, "author").id], status="sedimentation")
        guard_invitation_not_declined(session, a.id, rv.id)  # no invitation → no decline
        session.close()

    def test_guard_invitation_not_declined_raises(self, engine):
        from peerpedia_core.core.reviews.invite import invite_reviewer, decline_invitation
        session = get_session(engine)
        inviter = make_user(session, "inviter")
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[make_user(session, "author").id], status="sedimentation")
        _make_maintainer(session, a.id, inviter.id)
        invite_reviewer(session, article_id=a.id, inviter_id=inviter.id, invited_id=rv.id)
        decline_invitation(session, a.id, rv.id)
        with pytest.raises(BadRequestError, match="INVITATION_DECLINED"):
            guard_invitation_not_declined(session, a.id, rv.id)
        session.close()

    def test_guard_invitation_not_accepted_ok(self, engine):
        session = get_session(engine)
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[make_user(session, "author").id], status="sedimentation")
        guard_invitation_not_accepted(session, a.id, rv.id)  # no invitation → not accepted
        session.close()

    def test_guard_invitation_not_accepted_raises(self, engine):
        from peerpedia_core.core.reviews.invite import invite_reviewer, accept_invitation
        session = get_session(engine)
        inviter = make_user(session, "inviter")
        rv = make_user(session, "reviewer")
        a = make_article(session, authors=[make_user(session, "author").id], status="sedimentation")
        _make_maintainer(session, a.id, inviter.id)
        invite_reviewer(session, article_id=a.id, inviter_id=inviter.id, invited_id=rv.id)
        accept_invitation(session, a.id, rv.id)
        with pytest.raises(BadRequestError, match="INVITATION_ACCEPTED_ALREADY"):
            guard_invitation_not_accepted(session, a.id, rv.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# authorize_article_action (integration guard)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthorizeArticleAction:
    def test_happy_path(self, engine):
        session = get_session(engine)
        u = make_user(session, "author")
        a = make_article(session, authors=[u.id])
        _make_maintainer(session, a.id, u.id)
        user, article, mids = authorize_article_action(session, a.id, u.id)
        assert user.id == u.id
        assert article.id == a.id
        assert u.id in mids
        session.close()

    def test_user_not_found(self, engine):
        session = get_session(engine)
        a = make_article(session, authors=[make_user(session, "author").id])
        with pytest.raises(NotFoundError, match="USER_NOT_FOUND"):
            authorize_article_action(session, a.id, "nonexistent")
        session.close()

    def test_article_not_found(self, engine):
        session = get_session(engine)
        u = make_user(session, "user")
        with pytest.raises(NotFoundError, match="ARTICLE_NOT_FOUND"):
            authorize_article_action(session, "nonexistent", u.id)
        session.close()
