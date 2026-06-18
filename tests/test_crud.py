# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for CRUD operations — create, read, update, delete for all entities."""

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import (
    Article,
    Review,
    User,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_user(session: Session, name: str) -> User:
    u = User(username=f"test_{name}", password_hash="$2b$12$test", name=name, affiliation="Test", anonymous_name=f"anon_{name}")
    session.add(u)
    session.commit()
    return u


def _make_article(session: Session, authors: list[str], **kw) -> Article:
    from peerpedia_core.storage.db.models import ArticleAuthor

    a = Article(**kw)
    session.add(a)
    session.flush()
    for pos, aid in enumerate(authors):
        session.add(ArticleAuthor(article_id=a.id, author_id=aid, position=pos))
    session.commit()
    return a


def _default_scores():
    return {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3}


# ── Article CRUD ────────────────────────────────────────────────────────


class TestArticleCRUD:
    def test_create_article(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article

        session = get_session(engine)
        user = _make_user(session, "author1")
        article = create_article(session, authors=[user.id], status="draft")
        assert article.id is not None
        assert article.status == "draft"
        from peerpedia_core.storage.db.crud_article import get_author_ids

        assert get_author_ids(session, article.id) == [user.id]
        session.close()

    def test_get_article(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article, get_article

        session = get_session(engine)
        user = _make_user(session, "author2")
        a = create_article(session, authors=[user.id])
        assert get_article(session, a.id).id == a.id
        assert get_article(session, "nonexistent") is None
        session.close()

    def test_list_articles(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article, list_articles

        session = get_session(engine)
        user = _make_user(session, "author3")
        create_article(session, authors=[user.id], status="draft")
        create_article(session, authors=[user.id], status="published")
        create_article(session, authors=[user.id], status="sedimentation")
        # list all
        all_articles = list_articles(session)
        assert len(all_articles) == 3
        # filter by status
        published = list_articles(session, status="published")
        assert len(published) == 1
        assert published[0].status == "published"
        session.close()

    def test_update_article_status(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            get_article,
            update_article_status,
        )

        session = get_session(engine)
        user = _make_user(session, "author4")
        a = create_article(session, authors=[user.id], status="draft")
        update_article_status(session, a.id, "sedimentation")
        assert get_article(session, a.id).status == "sedimentation"
        session.close()

    def test_update_article_compiled_cache(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            get_article,
            update_article_compiled,
        )

        session = get_session(engine)
        user = _make_user(session, "author5")
        a = create_article(session, authors=[user.id])
        update_article_compiled(session, a.id, html_format="html", output="<h1>Hi</h1>", pages=None)
        a2 = get_article(session, a.id)
        assert a2.compiled_format == "html"
        assert a2.compiled_output == "<h1>Hi</h1>"
        session.close()

    def test_increment_fork_count(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            get_article,
            increment_fork_count,
        )

        session = get_session(engine)
        user = _make_user(session, "author6")
        a = create_article(session, authors=[user.id])
        increment_fork_count(session, a.id)
        assert get_article(session, a.id).fork_count == 1
        increment_fork_count(session, a.id)
        assert get_article(session, a.id).fork_count == 2
        session.close()

    def test_extend_sink_rejects_non_positive(self, engine):
        """Bug 8: extend_sink must reject extra_days <= 0."""
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            extend_sink,
        )

        session = get_session(engine)
        user = _make_user(session, "author8")
        a = create_article(session, authors=[user.id])
        with pytest.raises(ValueError):
            extend_sink(session, a.id, 0)
        with pytest.raises(ValueError):
            extend_sink(session, a.id, -1)
        session.close()

    def test_extend_sink_does_not_overcount_when_already_at_max(self, engine):
        """Bug 8: extend_sink counter should only increment when days actually increase."""
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            extend_sink,
            get_article,
        )

        session = get_session(engine)
        user = _make_user(session, "author8b")
        a = create_article(session, authors=[user.id])
        # Extend by 200, clamped to 180 (default max)
        extend_sink(session, a.id, 200)
        a2 = get_article(session, a.id)
        assert a2.sink_duration_days == 180
        assert a2.sink_extended_count == 1
        old_count = a2.sink_extended_count
        # Extend again, should be no-op (already at max), counter should NOT increment
        extend_sink(session, a.id, 10)
        a3 = get_article(session, a.id)
        assert a3.sink_duration_days == 180  # still max
        assert a3.sink_extended_count == old_count  # no change
        session.close()


# ── Review CRUD ──────────────────────────────────────────────────────────


class TestReviewCRUD:
    def test_create_review(self, engine):
        from peerpedia_core.storage.db.crud_review import create_review

        session = get_session(engine)
        reviewer = _make_user(session, "rv1")
        author = _make_user(session, "au1")
        article = _make_article(session, authors=[author.id])
        r = create_review(
            session, article_id=article.id, commit_hash="abc", reviewer_id=reviewer.id, scope="pool", scores=_default_scores()
        )
        assert r.id is not None
        assert r.scope == "pool"
        session.close()

    def test_get_reviews_for_article(self, engine):
        from peerpedia_core.storage.db.crud_review import (
            create_review,
            get_reviews_for_article,
        )

        session = get_session(engine)
        rv1 = _make_user(session, "rv_a")
        rv2 = _make_user(session, "rv_b")
        author = _make_user(session, "au_x")
        article = _make_article(session, authors=[author.id])
        create_review(
            session, article_id=article.id, commit_hash="h1", reviewer_id=rv1.id, scope="pool", scores=_default_scores()
        )
        create_review(
            session, article_id=article.id, commit_hash="h2", reviewer_id=rv2.id, scope="published", scores=_default_scores()
        )
        reviews = get_reviews_for_article(session, article.id)
        assert len(reviews) == 2
        session.close()

    def test_get_review_by_user_and_scope(self, engine):
        from peerpedia_core.storage.db.crud_review import (
            create_review,
            get_review_by_user_scope,
        )

        session = get_session(engine)
        rv = _make_user(session, "rv_s")
        author = _make_user(session, "au_s")
        article = _make_article(session, authors=[author.id])
        create_review(session, article_id=article.id, commit_hash="h", reviewer_id=rv.id, scope="pool", scores=_default_scores())
        found = get_review_by_user_scope(session, article.id, rv.id, "pool")
        assert found is not None
        assert found.reviewer_id == rv.id
        # different scope
        assert get_review_by_user_scope(session, article.id, rv.id, "published") is None
        session.close()

    def test_update_review_scores(self, engine):
        from peerpedia_core.storage.db.crud_review import (
            create_review,
            update_review_scores,
        )

        session = get_session(engine)
        rv = _make_user(session, "rv_u")
        author = _make_user(session, "au_u")
        article = _make_article(session, authors=[author.id])
        r = create_review(
            session, article_id=article.id, commit_hash="h", reviewer_id=rv.id, scope="pool", scores=_default_scores()
        )
        new_scores = {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 5, "impact": 5}
        update_review_scores(session, r.id, new_scores)
        updated = session.get(Review, r.id)
        assert updated.scores["originality"] == 5
        session.close()

    def test_review_different_commits_ok(self, engine):
        """Same (article, reviewer, scope) with different commit_hashes should succeed."""
        from peerpedia_core.storage.db.crud_review import create_review

        session = get_session(engine)
        rv = _make_user(session, "rv_multi")
        author = _make_user(session, "au_multi")
        article = _make_article(session, authors=[author.id])
        r1 = create_review(
            session, article_id=article.id, commit_hash="commit_1", reviewer_id=rv.id, scope="pool", scores=_default_scores()
        )
        r2 = create_review(
            session,
            article_id=article.id,
            commit_hash="commit_2",
            reviewer_id=rv.id,
            scope="pool",
            scores={
                "originality": 5,
                "rigor": 5,
                "completeness": 5,
                "pedagogy": 5,
                "impact": 5,
            },
        )
        assert r1.id != r2.id
        assert r1.commit_hash == "commit_1"
        assert r2.commit_hash == "commit_2"
        session.close()

    def test_duplicate_same_commit_fails(self, engine):
        """Same (article, reviewer, scope, commit_hash) must raise integrity error."""
        import sqlalchemy

        from peerpedia_core.storage.db.crud_review import create_review

        session = get_session(engine)
        rv = _make_user(session, "rv_dup")
        author = _make_user(session, "au_dup")
        article = _make_article(session, authors=[author.id])
        create_review(
            session, article_id=article.id, commit_hash="same_hash", reviewer_id=rv.id, scope="pool", scores=_default_scores()
        )
        with pytest.raises((sqlalchemy.exc.IntegrityError, Exception)):
            create_review(
                session,
                article_id=article.id,
                commit_hash="same_hash",
                reviewer_id=rv.id,
                scope="pool",
                scores={
                    "originality": 1,
                    "rigor": 1,
                    "completeness": 1,
                    "pedagogy": 1,
                    "impact": 1,
                },
            )
        session.close()

    def test_get_by_user_scope_with_commit(self, engine):
        """get_review_by_user_scope with commit_hash filters correctly."""
        from peerpedia_core.storage.db.crud_review import (
            create_review,
            get_review_by_user_scope,
        )

        session = get_session(engine)
        rv = _make_user(session, "rv_filt")
        author = _make_user(session, "au_filt")
        article = _make_article(session, authors=[author.id])
        create_review(session, article_id=article.id, commit_hash="h1", reviewer_id=rv.id, scope="pool", scores=_default_scores())
        create_review(
            session,
            article_id=article.id,
            commit_hash="h2",
            reviewer_id=rv.id,
            scope="pool",
            scores={
                "originality": 5,
                "rigor": 5,
                "completeness": 5,
                "pedagogy": 5,
                "impact": 5,
            },
        )
        found = get_review_by_user_scope(session, article.id, rv.id, "pool", commit_hash="h2")
        assert found is not None
        assert found.commit_hash == "h2"
        assert found.scores["originality"] == 5
        session.close()

    def test_add_thread_message(self, engine):
        from peerpedia_core.storage.db.crud_review import (
            add_thread_message,
            create_review,
        )

        session = get_session(engine)
        rv = _make_user(session, "rv_t")
        author = _make_user(session, "au_t")
        article = _make_article(session, authors=[author.id])
        r = create_review(
            session, article_id=article.id, commit_hash="h", reviewer_id=rv.id, scope="pool", scores=_default_scores()
        )
        from peerpedia_core.types.messages import ThreadMessage

        msg = ThreadMessage(author_id=author.id, content="谢谢指出，已修改。")
        add_thread_message(session, r.id, msg.to_dict())
        updated = session.get(Review, r.id)
        assert len(updated.thread) == 1
        assert "谢谢指出" in updated.thread[0]["content"]
        session.close()

    def test_upsert_review_updates_existing(self, engine):
        """upsert_review updates an existing review with same (article, reviewer, scope, commit_hash)."""
        from peerpedia_core.storage.db.crud_review import (
            create_review,
            upsert_review,
        )

        session = get_session(engine)
        rv = _make_user(session, "rv_upsert")
        author = _make_user(session, "au_upsert")
        article = _make_article(session, authors=[author.id])

        # Create initial review
        r1 = create_review(
            session,
            article_id=article.id,
            commit_hash="hash_u",
            reviewer_id=rv.id,
            scope="pool",
            scores={"originality": 1, "rigor": 1, "completeness": 1, "pedagogy": 1, "impact": 1},
        )

        # Upsert with same keys → should update
        new_scores = {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 5, "impact": 5}
        r2 = upsert_review(
            session, article_id=article.id, commit_hash="hash_u", reviewer_id=rv.id, scope="pool", scores=new_scores
        )
        assert r2.id == r1.id
        assert r2.scores["originality"] == 5
        session.close()


# ── User CRUD ────────────────────────────────────────────────────────────


class TestUserCRUD:
    def test_create_user(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user

        session = get_session(engine)
        u = create_user(session, name="新用户", affiliation="某大学")
        assert u.id is not None
        assert u.name == "新用户"
        assert u.anonymous_name != ""  # 自动生成
        session.close()

    def test_get_user(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, get_user

        session = get_session(engine)
        u = create_user(session, name="test")
        assert get_user(session, u.id).name == "test"
        assert get_user(session, "nonexistent") is None
        session.close()

    def test_list_users(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_users

        session = get_session(engine)
        create_user(session, name="张三")
        create_user(session, name="李四")
        assert len(list_users(session)) == 2
        session.close()

    def test_update_user_reputation(self, engine):
        from peerpedia_core.storage.db.crud_user import (
            create_user,
            get_user,
            update_user_reputation,
        )

        session = get_session(engine)
        u = create_user(session, name="rep_user")
        rep = {"professionalism": 4.0, "objectivity": 3.5, "collaboration": 4.5, "pedagogy": 4.0}
        update_user_reputation(session, u.id, rep)
        assert get_user(session, u.id).reputation == rep
        session.close()


# ── Follow CRUD ──────────────────────────────────────────────────────────


class TestFollowCRUD:
    def test_follow_unfollow(self, engine):
        from peerpedia_core.storage.db.crud_user import (
            create_user,
            follow_user,
            is_following,
            unfollow_user,
        )

        session = get_session(engine)
        a = create_user(session, name="A")
        b = create_user(session, name="B")
        follow_user(session, a.id, b.id)
        assert is_following(session, a.id, b.id) is True
        assert is_following(session, b.id, a.id) is False
        unfollow_user(session, a.id, b.id)
        assert is_following(session, a.id, b.id) is False
        session.close()

    def test_get_followers_following(self, engine):
        from peerpedia_core.storage.db.crud_user import (
            create_user,
            follow_user,
            get_follower_count,
            get_followers,
            get_following,
            get_following_count,
        )

        session = get_session(engine)
        a = create_user(session, name="A")
        b = create_user(session, name="B")
        c = create_user(session, name="C")
        follow_user(session, b.id, a.id)  # b follows a
        follow_user(session, c.id, a.id)  # c follows a
        assert get_follower_count(session, a.id) == 2
        assert get_following_count(session, b.id) == 1
        followers = get_followers(session, a.id)
        assert len(followers) == 2
        following = get_following(session, c.id)
        assert len(following) == 1
        session.close()

    def test_follow_user_rejects_self_follow(self, engine):
        """Bug 10: follow_user must reject when follower_id == followed_id."""
        from peerpedia_core.storage.db.crud_user import (
            create_user,
            follow_user,
        )

        session = get_session(engine)
        a = create_user(session, name="A")
        with pytest.raises(ValueError, match="cannot follow themselves"):
            follow_user(session, a.id, a.id)
        session.close()


# ── Bookmark CRUD ────────────────────────────────────────────────────────


class TestBookmarkCRUD:
    def test_bookmark_crud(self, engine):
        from peerpedia_core.storage.db.crud_bookmark import (
            add_bookmark,
            get_bookmarks_for_user,
            is_bookmarked,
            remove_bookmark,
        )

        session = get_session(engine)
        user = _make_user(session, "reader")
        author = _make_user(session, "writer")
        a1 = _make_article(session, authors=[author.id])
        a2 = _make_article(session, authors=[author.id])
        add_bookmark(session, user.id, a1.id)
        add_bookmark(session, user.id, a2.id)
        assert is_bookmarked(session, user.id, a1.id) is True
        bookmarks = get_bookmarks_for_user(session, user.id)
        assert len(bookmarks) == 2
        remove_bookmark(session, user.id, a1.id)
        assert is_bookmarked(session, user.id, a1.id) is False
        assert len(get_bookmarks_for_user(session, user.id)) == 1
        session.close()


# ── Merge Proposal CRUD ─────────────────────────────────────────────────


class TestMergeProposalCRUD:
    def test_create_and_get(self, engine):
        from peerpedia_core.storage.db.crud_merge import (
            create_merge_proposal,
            get_merge_proposal,
            get_merge_proposals_for_article,
        )

        session = get_session(engine)
        author = _make_user(session, "mp_author")
        forker = _make_user(session, "mp_forker")
        original = _make_article(session, authors=[author.id])
        fork = _make_article(session, authors=[forker.id])
        mp = create_merge_proposal(session, fork_id=fork.id, target_id=original.id, proposer_id=forker.id)
        assert mp.status == "open"
        assert get_merge_proposal(session, mp.id).proposer_id == forker.id
        proposals = get_merge_proposals_for_article(session, original.id)
        assert len(proposals) == 1
        session.close()

    def test_accept_reject(self, engine):
        from peerpedia_core.storage.db.crud_merge import (
            accept_merge_proposal,
            create_merge_proposal,
            get_merge_proposal,
        )

        session = get_session(engine)
        author = _make_user(session, "mp_a2")
        forker = _make_user(session, "mp_f2")
        original = _make_article(session, authors=[author.id])
        fork = _make_article(session, authors=[forker.id])
        mp = create_merge_proposal(session, fork_id=fork.id, target_id=original.id, proposer_id=forker.id)
        accept_merge_proposal(session, mp.id)
        assert get_merge_proposal(session, mp.id).status == "accepted"
        # can't re-accept
        with pytest.raises(ValueError):
            accept_merge_proposal(session, mp.id)
        session.close()

    def test_add_thread_message(self, engine):
        from peerpedia_core.storage.db.crud_merge import (
            add_merge_thread_message,
            create_merge_proposal,
            get_merge_proposal,
        )

        session = get_session(engine)
        author = _make_user(session, "mp_a3")
        forker = _make_user(session, "mp_f3")
        original = _make_article(session, authors=[author.id])
        fork = _make_article(session, authors=[forker.id])
        mp = create_merge_proposal(session, fork_id=fork.id, target_id=original.id, proposer_id=forker.id)
        from peerpedia_core.types.messages import ThreadMessage

        msg = ThreadMessage(author_id=forker.id, content="请审阅合并。")
        add_merge_thread_message(session, mp.id, msg.to_dict())
        updated = get_merge_proposal(session, mp.id)
        assert len(updated.thread) == 1
        session.close()

    def test_create_merge_proposal_rejects_self(self, engine):
        """Bug 11: create_merge_proposal must reject when fork_id == target_id."""
        from peerpedia_core.storage.db.crud_merge import (
            create_merge_proposal,
        )

        session = get_session(engine)
        author = _make_user(session, "mp_sr")
        article = _make_article(session, authors=[author.id])
        with pytest.raises(ValueError, match="Cannot create a merge proposal for an article with itself"):
            create_merge_proposal(session, fork_id=article.id, target_id=article.id, proposer_id=author.id)
        session.close()


# ── Citation CRUD ───────────────────────────────────────────────────────


class TestCitationCRUD:
    def test_create_and_update(self, engine):
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation,
            get_cited_by,
            get_cites,
        )

        session = get_session(engine)
        author = _make_user(session, "cit_author")
        a1 = _make_article(session, authors=[author.id])
        a2 = _make_article(session, authors=[author.id])
        a3 = _make_article(session, authors=[author.id])
        create_or_update_citation(session, a1.id, a2.id, forward=0.5, backward=0.2)
        create_or_update_citation(session, a1.id, a3.id, forward=0.3, backward=0.1)
        cites = get_cites(session, a1.id)
        assert len(cites) == 2
        cited_by = get_cited_by(session, a2.id)
        assert len(cited_by) == 1
        assert cited_by[0].from_article_id == a1.id
        session.close()

    def test_update_probabilities(self, engine):
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation,
            get_citation,
        )

        session = get_session(engine)
        author = _make_user(session, "cp_au")
        a1 = _make_article(session, authors=[author.id])
        a2 = _make_article(session, authors=[author.id])
        create_or_update_citation(session, a1.id, a2.id, forward=0.1, backward=0.1)
        c = get_citation(session, a1.id, a2.id)
        assert c.forward_prob == 0.1
        create_or_update_citation(session, a1.id, a2.id, forward=0.9, backward=0.05)
        c2 = get_citation(session, a1.id, a2.id)
        assert c2.forward_prob == 0.9
        session.close()

    def test_create_or_update_citation_rejects_self_reference(self, engine):
        """Bug 9: create_or_update_citation must reject from_id == to_id."""
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation,
        )

        session = get_session(engine)
        author = _make_user(session, "cit_sr")
        a1 = _make_article(session, authors=[author.id])
        with pytest.raises(ValueError):
            create_or_update_citation(session, a1.id, a1.id)
        session.close()

    def test_get_citations_all_edges(self, engine):
        """get_citations returns both incoming and outgoing edges."""
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation,
            get_citations,
        )

        session = get_session(engine)
        author = _make_user(session, "cit_gc")
        a1 = _make_article(session, authors=[author.id])
        a2 = _make_article(session, authors=[author.id])
        a3 = _make_article(session, authors=[author.id])
        create_or_update_citation(session, a1.id, a2.id)  # a1 cites a2
        create_or_update_citation(session, a3.id, a1.id)  # a3 cites a1
        edges = get_citations(session, a1.id)
        assert len(edges) == 2
        session.close()


# ── Update not-found edge cases ──────────────────────────────────────────


class TestUpdateNotFound:
    """ValueError raised when updating non-existent entities."""

    def test_update_article_compiled_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import update_article_compiled

        session = get_session(engine)
        with pytest.raises(ValueError, match="not found"):
            update_article_compiled(session, "no-such-id", "html", "hi", None)
        session.close()

    def test_update_article_status_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import update_article_status

        session = get_session(engine)
        with pytest.raises(ValueError):
            update_article_status(session, "no-such-id", "published")
        session.close()

    def test_increment_fork_count_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import increment_fork_count

        session = get_session(engine)
        with pytest.raises(ValueError):
            increment_fork_count(session, "no-such-id")
        session.close()

    def test_set_sink_start_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import set_sink_start

        session = get_session(engine)
        with pytest.raises(ValueError):
            set_sink_start(session, "no-such-id", 7)
        session.close()

    def test_delete_article_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import delete_article

        session = get_session(engine)
        with pytest.raises(ValueError):
            delete_article(session, "no-such-id")
        session.close()

    def test_extend_sink_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import extend_sink

        session = get_session(engine)
        with pytest.raises(ValueError):
            extend_sink(session, "no-such-id", 5)
        session.close()

    def test_update_user_reputation_not_found(self, engine):
        from peerpedia_core.storage.db.crud_user import update_user_reputation

        session = get_session(engine)
        with pytest.raises(ValueError):
            update_user_reputation(session, "no-such-id", {})
        session.close()

    def test_update_review_scores_not_found(self, engine):
        from peerpedia_core.storage.db.crud_review import update_review_scores

        session = get_session(engine)
        with pytest.raises(ValueError):
            update_review_scores(session, "no-such-id", {})
        session.close()

    def test_add_thread_message_review_not_found(self, engine):
        from peerpedia_core.storage.db.crud_review import add_thread_message

        session = get_session(engine)
        with pytest.raises(ValueError):
            add_thread_message(session, "no-such-id", {"content": "test"})
        session.close()

    def test_resolve_merge_not_found(self, engine):
        from peerpedia_core.storage.db.crud_merge import _resolve

        session = get_session(engine)
        with pytest.raises(ValueError):
            _resolve(session, "no-such-id", "accepted")
        session.close()

    def test_add_merge_thread_message_not_found(self, engine):
        from peerpedia_core.storage.db.crud_merge import add_merge_thread_message

        session = get_session(engine)
        with pytest.raises(ValueError):
            add_merge_thread_message(session, "no-such-id", {"content": "test"})
        session.close()
