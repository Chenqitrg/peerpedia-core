# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for cleaned DB models — Article, Review, User, Follow, Bookmark,
MergeProposal, Citation."""

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import (
    Article,
    Bookmark,
    Citation,
    Follow,
    MergeProposal,
    Review,
    User,
)
from peerpedia_core.types.messages import ThreadMessage

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_user(session: Session, name: str, **kwargs) -> User:
    u = User(
        username=f"test_{name}",
        password_hash="$2b$12$test",
        name=name,
        affiliation=kwargs.pop("affiliation", "Test"),
        anonymous_name=kwargs.pop("anonymous_name", f"anon_{name}"),
        **kwargs,
    )
    session.add(u)
    session.commit()
    return u


def _make_article(session: Session, **kwargs) -> Article:
    from peerpedia_core.storage.db.models import ArticleAuthor

    author_ids = kwargs.pop("authors", [])
    a = Article(
        status=kwargs.pop("status", "draft"),
        forked_from=kwargs.pop("forked_from", None),
        **kwargs,
    )
    session.add(a)
    session.flush()  # ensure a.id is available
    for pos, aid in enumerate(author_ids):
        session.add(ArticleAuthor(article_id=a.id, author_id=aid, position=pos))
    session.commit()
    return a


# ── Article ──────────────────────────────────────────────────────────────


class TestArticle:
    """文章模型 — git 管内容，数据库管元数据"""

    def test_create_minimal(self, engine):
        from peerpedia_core.storage.db.crud_article import get_author_ids
        from peerpedia_core.storage.db.models import ArticleAuthor

        session = get_session(engine)
        user = _make_user(session, "testuser")
        a = Article(status="draft")
        session.add(a)
        session.flush()
        session.add(ArticleAuthor(article_id=a.id, author_id=user.id, position=0))
        session.commit()

        assert a.id is not None
        assert a.status == "draft"
        assert get_author_ids(session, a.id) == [user.id]
        assert a.score is None
        assert a.compiled_format is None
        assert a.sink_start is None
        assert a.sink_duration_days == 7
        assert a.sink_extended_count == 0
        assert a.fork_count == 0
        session.close()

    def test_status_valid_values(self, engine):
        session = get_session(engine)
        user = _make_user(session, "u1")
        for status in ("draft", "sedimentation", "published"):
            a = _make_article(session, status=status, authors=[user.id])
            assert a.status == status
        session.close()

    def test_score_stores_dict(self, engine):
        """JSONDict column stores score as dict, FiveDimScores wraps it."""
        session = get_session(engine)
        user = _make_user(session, "u3")
        score_dict = {"originality": 4.0, "rigor": 3.0, "completeness": 5.0, "pedagogy": 2.0, "impact": 4.0}
        a = _make_article(session, status="published", authors=[user.id], score=score_dict)
        a2 = session.get(Article, a.id)
        assert a2.score == score_dict
        assert a2.score["originality"] == 4.0
        session.close()

    def test_compiled_cache_for_html(self, engine):
        session = get_session(engine)
        user = _make_user(session, "u4")
        a = _make_article(session, status="published", authors=[user.id], compiled_format="html", compiled_output="<h1>Test</h1>")
        a2 = session.get(Article, a.id)
        assert a2.compiled_format == "html"
        assert a2.compiled_output == "<h1>Test</h1>"
        session.close()

    def test_compiled_cache_for_svg(self, engine):
        session = get_session(engine)
        user = _make_user(session, "u5")
        a = _make_article(
            session,
            status="published",
            authors=[user.id],
            compiled_format="svg",
            compiled_output=None,
            compiled_pages=["<svg>p1</svg>", "<svg>p2</svg>"],
        )
        a2 = session.get(Article, a.id)
        assert a2.compiled_format == "svg"
        assert a2.compiled_pages == ["<svg>p1</svg>", "<svg>p2</svg>"]
        session.close()

    def test_fork_tracking(self, engine):
        session = get_session(engine)
        user = _make_user(session, "u6")
        original = _make_article(session, status="published", authors=[user.id])
        fork = _make_article(session, status="draft", forked_from=original.id, authors=[user.id])
        session.add(fork)
        session.commit()
        assert fork.forked_from == original.id
        original.fork_count += 1
        session.commit()
        o2 = session.get(Article, original.id)
        assert o2.fork_count == 1
        session.close()

    def test_article_updated_at_updates_on_change(self, engine):
        """Bug 6: Article.updated_at has onupdate so it refreshes on each commit."""
        session = get_session(engine)
        user = _make_user(session, "u7")
        a = _make_article(session, status="draft", authors=[user.id])
        original_updated = a.updated_at
        # Mutate and commit
        a.status = "published"
        session.commit()
        # Ensure updated_at changed
        assert a.updated_at > original_updated


# ── Review ───────────────────────────────────────────────────────────────


class TestReview:
    """评审 + 对话线程"""

    def test_create_review(self, engine):
        session = get_session(engine)
        user = _make_user(session, "reviewer")
        author = _make_user(session, "author")
        article = _make_article(session, status="sedimentation", authors=[author.id])
        review = Review(
            article_id=article.id,
            commit_hash="abc123",
            reviewer_id=user.id,
            scope="pool",
            scores={"originality": 4.0, "rigor": 3.0, "completeness": 4.0, "pedagogy": 3.0, "impact": 3.5},
        )
        session.add(review)
        session.commit()
        r = session.get(Review, review.id)
        assert r.article_id == article.id
        assert r.commit_hash == "abc123"
        assert r.scope == "pool"
        assert r.scores["originality"] == 4.0
        assert r.thread == []
        session.close()

    def test_both_scopes_for_same_reviewer(self, engine):
        session = get_session(engine)
        user = _make_user(session, "rv")
        author = _make_user(session, "au")
        article = _make_article(session, status="published", authors=[author.id])
        r1 = Review(
            article_id=article.id,
            commit_hash="h1",
            reviewer_id=user.id,
            scope="pool",
            scores={"originality": 1.0, "rigor": 1.0, "completeness": 1.0, "pedagogy": 1.0, "impact": 1.0},
        )
        r2 = Review(
            article_id=article.id,
            commit_hash="h2",
            reviewer_id=user.id,
            scope="published",
            scores={"originality": 2.0, "rigor": 2.0, "completeness": 2.0, "pedagogy": 2.0, "impact": 2.0},
        )
        session.add_all([r1, r2])
        session.commit()
        assert r1.scope != r2.scope
        session.close()

    def test_unique_constraint_per_scope(self, engine):
        """同一 (article, reviewer, scope) 组合不能重复"""
        session = get_session(engine)
        author = _make_user(session, "au3")
        reviewer = _make_user(session, "rv3")
        article = _make_article(session, status="published", authors=[author.id])
        r1 = Review(
            article_id=article.id,
            commit_hash="h",
            reviewer_id=reviewer.id,
            scope="pool",
            scores={"originality": 1, "rigor": 1, "completeness": 1, "pedagogy": 1, "impact": 1},
        )
        session.add(r1)
        session.commit()
        r2 = Review(
            article_id=article.id,
            commit_hash="h",
            reviewer_id=reviewer.id,
            scope="pool",
            scores={"originality": 2, "rigor": 2, "completeness": 2, "pedagogy": 2, "impact": 2},
        )
        session.add(r2)
        with pytest.raises(Exception):
            session.commit()
        session.close()

    def test_thread_stored_as_dict_list(self, engine):
        session = get_session(engine)
        author = _make_user(session, "au2")
        reviewer = _make_user(session, "rv2")
        article = _make_article(session, status="published", authors=[author.id])
        msg = ThreadMessage(author_id=reviewer.id, content="需要补充证明。")
        review = Review(
            article_id=article.id,
            commit_hash="abc",
            reviewer_id=reviewer.id,
            scope="published",
            scores={"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            thread=[msg.to_dict()],
        )
        session.add(review)
        session.commit()
        r = session.get(Review, review.id)
        assert len(r.thread) == 1
        assert r.thread[0]["author_id"] == reviewer.id
        assert "证明" in r.thread[0]["content"]
        session.close()

    def test_self_review_is_just_a_review(self, engine):
        session = get_session(engine)
        author = _make_user(session, "self_author")
        article = _make_article(session, status="sedimentation", authors=[author.id])
        review = Review(
            article_id=article.id,
            commit_hash="init",
            reviewer_id=author.id,
            scope="pool",
            scores={"originality": 4.5, "rigor": 3.0, "completeness": 4.0, "pedagogy": 5.0, "impact": 4.0},
        )
        session.add(review)
        session.commit()
        from peerpedia_core.storage.db.crud_article import get_author_ids

        assert review.reviewer_id in get_author_ids(session, article.id)  # 这就是自评
        session.close()

    def test_review_updated_at_updates_on_change(self, engine):
        """Bug 7: Review.updated_at has onupdate so it refreshes on each commit."""
        session = get_session(engine)
        user = _make_user(session, "rv_up")
        author = _make_user(session, "au_up")
        article = _make_article(session, status="sedimentation", authors=[author.id])
        review = Review(
            article_id=article.id,
            commit_hash="init",
            reviewer_id=user.id,
            scope="pool",
            scores={"originality": 3.0, "rigor": 3.0, "completeness": 3.0, "pedagogy": 3.0, "impact": 3.0},
        )
        session.add(review)
        session.commit()
        original_updated = review.updated_at
        # Mutate and commit
        review.scope = "published"
        session.commit()
        assert review.updated_at > original_updated
        session.close()


# ── User ─────────────────────────────────────────────────────────────────


class TestUserModel:
    def test_create_user(self, engine):
        session = get_session(engine)
        u = User(
            username="zhangsan",
            password_hash="$2b$12$test",
            name="张三",
            anonymous_name="星云评审员",
            affiliation="清华大学",
            expertise=["理论物理", "数学"],
            reputation={"professionalism": 3.5, "objectivity": 4.0, "collaboration": 2.0, "pedagogy": 4.5},
        )
        session.add(u)
        session.commit()
        u2 = session.get(User, u.id)
        assert u2.name == "张三"
        assert u2.anonymous_name == "星云评审员"
        assert u2.expertise == ["理论物理", "数学"]
        assert u2.reputation["objectivity"] == 4.0
        session.close()

    def test_default_reputation(self, engine):
        session = get_session(engine)
        u = User(username="lisi", password_hash="$2b$12$test", name="李四", anonymous_name="anon_li")
        session.add(u)
        session.commit()
        u2 = session.get(User, u.id)
        assert u2.reputation is not None
        session.close()


# ── Follow ───────────────────────────────────────────────────────────────


class TestFollow:
    def test_follow_relationship(self, engine):
        session = get_session(engine)
        a = _make_user(session, "follower")
        b = _make_user(session, "target")
        f = Follow(follower_id=a.id, followed_id=b.id)
        session.add(f)
        session.commit()
        assert f.follower_id == a.id
        assert f.followed_id == b.id
        session.close()

    def test_unique_follow(self, engine):
        session = get_session(engine)
        a = _make_user(session, "fa")
        b = _make_user(session, "fb")
        session.add(Follow(follower_id=a.id, followed_id=b.id))
        session.commit()
        session.add(Follow(follower_id=a.id, followed_id=b.id))
        with pytest.raises(Exception):
            session.commit()
        session.close()


# ── Bookmark ─────────────────────────────────────────────────────────────


class TestBookmark:
    def test_bookmark_article(self, engine):
        session = get_session(engine)
        user = _make_user(session, "reader")
        author = _make_user(session, "writer")
        article = _make_article(session, status="published", authors=[author.id])
        b = Bookmark(user_id=user.id, article_id=article.id)
        session.add(b)
        session.commit()
        assert b.user_id == user.id
        assert b.article_id == article.id
        session.close()

    def test_unique_bookmark(self, engine):
        session = get_session(engine)
        user = _make_user(session, "r2")
        author = _make_user(session, "w2")
        article = _make_article(session, status="published", authors=[author.id])
        session.add(Bookmark(user_id=user.id, article_id=article.id))
        session.commit()
        session.add(Bookmark(user_id=user.id, article_id=article.id))
        with pytest.raises(Exception):
            session.commit()
        session.close()


# ── MergeProposal ────────────────────────────────────────────────────────


class TestMergeProposal:
    def test_create_merge_proposal(self, engine):
        session = get_session(engine)
        author = _make_user(session, "original_author")
        forker = _make_user(session, "forker")
        original = _make_article(session, status="published", authors=[author.id])
        fork = _make_article(session, status="draft", authors=[forker.id], forked_from=original.id)
        mp = MergeProposal(fork_article_id=fork.id, target_article_id=original.id, proposer_id=forker.id, status="open")
        session.add(mp)
        session.commit()
        assert mp.proposer_id == forker.id
        assert mp.status == "open"
        assert mp.thread == []
        session.close()

    def test_merge_thread(self, engine):
        session = get_session(engine)
        author = _make_user(session, "oa2")
        forker = _make_user(session, "fo2")
        original = _make_article(session, status="published", authors=[author.id])
        fork = _make_article(session, status="draft", authors=[forker.id], forked_from=original.id)
        mp = MergeProposal(
            fork_article_id=fork.id,
            target_article_id=original.id,
            proposer_id=forker.id,
            status="open",
            thread=[
                ThreadMessage(author_id=forker.id, content="请求合并，补充了第三章。").to_dict(),
                ThreadMessage(author_id=author.id, content="收到，我看看。").to_dict(),
            ],
        )
        session.add(mp)
        session.commit()
        m2 = session.get(MergeProposal, mp.id)
        assert len(m2.thread) == 2
        session.close()

    def test_valid_statuses(self, engine):
        session = get_session(engine)
        author = _make_user(session, "oa3")
        forker = _make_user(session, "fo3")
        original = _make_article(session, status="published", authors=[author.id])
        fork = _make_article(session, status="draft", authors=[forker.id], forked_from=original.id)
        mp = MergeProposal(fork_article_id=fork.id, target_article_id=original.id, proposer_id=forker.id, status="open")
        session.add(mp)
        session.commit()
        for status in ("accepted", "rejected"):
            mp.status = status
            session.commit()
            assert session.get(MergeProposal, mp.id).status == status
        session.close()


# ── Citation ─────────────────────────────────────────────────────────────


class TestCitation:
    def test_citation_edge(self, engine):
        session = get_session(engine)
        author = _make_user(session, "cit_author")
        a1 = _make_article(session, status="published", authors=[author.id])
        a2 = _make_article(session, status="published", authors=[author.id])
        c = Citation(from_article_id=a1.id, to_article_id=a2.id, forward_prob=0.3, backward_prob=0.1)
        session.add(c)
        session.commit()
        assert c.from_article_id == a1.id
        assert c.to_article_id == a2.id
        assert c.forward_prob == 0.3
        assert c.backward_prob == 0.1
        session.close()

    def test_unique_citation(self, engine):
        session = get_session(engine)
        author = _make_user(session, "cit_a2")
        a1 = _make_article(session, status="published", authors=[author.id])
        a2 = _make_article(session, status="published", authors=[author.id])
        session.add(Citation(from_article_id=a1.id, to_article_id=a2.id))
        session.commit()
        session.add(Citation(from_article_id=a1.id, to_article_id=a2.id))
        with pytest.raises(Exception):
            session.commit()
        session.close()
