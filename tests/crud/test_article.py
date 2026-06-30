# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for ArticleMetaStorage CRUD — create, read, list, update, delete."""

import uuid

import pytest

from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import (
    ArticleAuthorStorage, ArticleMetaStorage, BookmarkStorage, FollowStorage, UserStorage,
)
from tests.crud.conftest import default_scores, make_article, make_user


def _user(**kwargs):
    """Create a UserStorage with required fields filled in."""
    defaults = {
        "id": str(uuid.uuid4()),
        "public_key": "0000000000000000000000000000000000000000000000000000000000000000",
        "name": "Test User",
        "affiliation": "Test",
    }
    defaults.update(kwargs)
    return UserStorage(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# Core CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleCRUD:
    def test_create_article(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article

        session = get_session(engine)
        user = make_user(session, "author1")
        article = create_article(session, title="", authors=[user.id], status="draft")
        assert article.id is not None
        assert article.status == "draft"
        from peerpedia_core.storage.db.crud_author import list_author_ids

        assert list_author_ids(session, article.id) == [user.id]
        session.close()

    def test_get_article(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article, get_article

        session = get_session(engine)
        user = make_user(session, "author2")
        a = create_article(session, title="", authors=[user.id])
        assert get_article(session, a.id).id == a.id
        assert get_article(session, "nonexistent") is None
        session.close()

    def test_list_articles(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article, list_articles

        session = get_session(engine)
        user = make_user(session, "author3")
        create_article(session, title="", authors=[user.id], status="draft")
        create_article(session, title="", authors=[user.id], status="published")
        create_article(session, title="", authors=[user.id], status="sedimentation")
        all_articles = list_articles(session)
        assert len(all_articles) == 3
        published = list_articles(session, statuses={"published"})
        assert len(published) == 1
        assert published[0].status == "published"
        session.close()

    def test_update_article_status(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article, get_article, update_article_status,
        )

        session = get_session(engine)
        user = make_user(session, "author4")
        a = create_article(session, title="", authors=[user.id], status="draft")
        update_article_status(session, a.id, "sedimentation")
        assert get_article(session, a.id).status == "sedimentation"
        session.close()

    def test_invalid_status_rejected(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article, update_article_status

        session = get_session(engine)
        user = make_user(session, "author_inv")
        a = create_article(session, title="", authors=[user.id], status="draft")
        with pytest.raises(BadRequestError, match="INVALID_ARTICLE_STATUS"):
            update_article_status(session, a.id, "bogus")
        session.close()

    def test_update_article_compiled_cache(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article, get_article, update_article_compiled,
        )

        session = get_session(engine)
        user = make_user(session, "author5")
        a = create_article(session, title="", authors=[user.id])
        update_article_compiled(session, a.id, html_format="html", output="<h1>Hi</h1>", pages=None)
        a2 = get_article(session, a.id)
        assert a2.compiled_format == "html"
        assert a2.compiled_output == "<h1>Hi</h1>"
        session.close()

    def test_increment_fork_count(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article, get_article, increment_fork_count,
        )

        session = get_session(engine)
        user = make_user(session, "author6")
        a = create_article(session, title="", authors=[user.id])
        increment_fork_count(session, a.id)
        assert get_article(session, a.id).fork_count == 1
        increment_fork_count(session, a.id)
        assert get_article(session, a.id).fork_count == 2
        session.close()

    def test_extend_sink_rejects_non_positive(self, engine):
        from peerpedia_core.storage.db.crud_article import create_article, extend_sink

        session = get_session(engine)
        user = make_user(session, "author8")
        a = create_article(session, title="", authors=[user.id])
        with pytest.raises(ValueError):
            extend_sink(session, a.id, 0)
        with pytest.raises(ValueError):
            extend_sink(session, a.id, -1)
        session.close()

    def test_extend_sink_does_not_overcount_when_already_at_max(self, engine):
        from peerpedia_core.storage.db.crud_article import (
            create_article, extend_sink, get_article,
        )

        session = get_session(engine)
        user = make_user(session, "author8b")
        a = create_article(session, title="", authors=[user.id])
        extend_sink(session, a.id, 200)
        a2 = get_article(session, a.id)
        assert a2.sink_duration_days == 180
        assert a2.sink_extended_count == 1
        old_count = a2.sink_extended_count
        extend_sink(session, a.id, 10)
        a3 = get_article(session, a.id)
        assert a3.sink_duration_days == 180
        assert a3.sink_extended_count == old_count
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Not-found error paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleNotFound:
    def test_update_article_compiled_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import update_article_compiled

        session = get_session(engine)
        with pytest.raises(NotFoundError, match="ARTICLE_NOT_FOUND"):
            update_article_compiled(session, "no-such-id", "html", "hi", None)
        session.close()

    def test_update_article_status_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import update_article_status

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            update_article_status(session, "no-such-id", "published")
        session.close()

    def test_increment_fork_count_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import increment_fork_count

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            increment_fork_count(session, "no-such-id")
        session.close()

    def test_set_sink_start_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import set_sink_start

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            set_sink_start(session, "no-such-id", 7)
        session.close()

    def test_delete_article_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import delete_article

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            delete_article(session, "no-such-id")
        session.close()

    def test_extend_sink_not_found(self, engine):
        from peerpedia_core.storage.db.crud_article import extend_sink

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            extend_sink(session, "no-such-id", 5)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# list_articles — full parameter coverage
# ═══════════════════════════════════════════════════════════════════════════════


class TestListArticles:
    """Every parameter of ``list_articles`` is exercised, alone and in combination."""

    # ── statuses ────────────────────────────────────────────────────────────

    def test_empty_status_set_returns_all(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-lm1", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-lm2", status="published", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        assert len(list_articles(s, statuses=set())) == 2

    def test_no_statuses_default_returns_all(self, db_engine):
        """statuses=None (the default) returns everything — no filter applied."""
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-nf1", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-nf2", status="published", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-nf3", status="sedimentation", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        assert len(list_articles(s)) == 3

    def test_filters_by_single_status(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-lm3", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-lm4", status="published", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        result = list_articles(s, statuses={"published"})
        assert [r.id for r in result] == ["a-lm4"]

    def test_filters_by_multiple_statuses(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-lm5", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-lm6", status="sedimentation", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-lm7", status="published", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        result = list_articles(s, statuses={"draft", "sedimentation"})
        assert {r.id for r in result} == {"a-lm5", "a-lm6"}

    # ── search_query (ILIKE) ────────────────────────────────────────────────

    def test_search_query_partial_match(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="Quantum Entanglement Basics", id="a-sq1", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="Classical Mechanics", id="a-sq2", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="Advanced Quantum Field Theory", id="a-sq3", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        result = list_articles(s, search_query="quantum")
        assert {r.id for r in result} == {"a-sq1", "a-sq3"}

    def test_search_query_case_insensitive(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="MACHINE LEARNING", id="a-sci1", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        result = list_articles(s, search_query="machine")
        assert len(result) == 1
        assert result[0].id == "a-sci1"

    def test_search_query_no_match_returns_empty(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="Foo", id="a-sn1", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        assert list_articles(s, search_query="nonexistent") == []

    # ── id_prefix ───────────────────────────────────────────────────────────

    def test_id_prefix_match(self, db_engine):
        s = get_session(db_engine)
        pid = "abcd1234-0000-0000-0000-000000000001"
        s.add(ArticleMetaStorage(title="", id=pid, status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="abcd1234-0000-0000-0000-000000000002", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="zzzz1234-0000-0000-0000-000000000003", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        result = list_articles(s, id_prefix="abcd1234")
        assert len(result) == 2

    def test_id_prefix_no_match_returns_empty(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="eeeeeeee-0000-0000-0000-000000000001", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        assert list_articles(s, id_prefix="00000000") == []

    # ── author_ids ──────────────────────────────────────────────────────────

    def test_filters_by_author_ids(self, db_engine):
        """Direct CRUD call with author_ids — no core wrapper."""
        from peerpedia_core.storage.db.crud_article import list_articles
        s = get_session(db_engine)
        u1 = _user(id="u-la1")
        u2 = _user(id="u-la2")
        s.add(u1)
        s.add(u2)
        a1 = ArticleMetaStorage(title="", id="a-la1", status="draft", fork_count=0)
        a2 = ArticleMetaStorage(title="", id="a-la2", status="draft", fork_count=0)
        s.add_all([a1, a2])
        s.flush()
        s.add(ArticleAuthorStorage(article_id="a-la1", author_id="u-la1", position=0))
        s.add(ArticleAuthorStorage(article_id="a-la2", author_id="u-la2", position=0))
        s.commit()
        result = list_articles(s, author_ids={"u-la1"})
        assert [r.id for r in result] == ["a-la1"]

    def test_author_ids_with_statuses_combined(self, db_engine):
        """AND filter: author_ids ∩ statuses."""
        from peerpedia_core.storage.db.crud_article import list_articles
        s = get_session(db_engine)
        u = _user(id="u-combo")
        s.add(u)
        a1 = ArticleMetaStorage(title="", id="a-co1", status="draft", fork_count=0)
        a2 = ArticleMetaStorage(title="", id="a-co2", status="published", fork_count=0)
        s.add_all([a1, a2])
        s.flush()
        s.add(ArticleAuthorStorage(article_id="a-co1", author_id="u-combo", position=0))
        s.add(ArticleAuthorStorage(article_id="a-co2", author_id="u-combo", position=0))
        s.commit()
        result = list_articles(s, author_ids={"u-combo"}, statuses={"published"})
        assert [r.id for r in result] == ["a-co2"]

    # ── viewer_id (follower feed) ───────────────────────────────────────────

    def test_viewer_id_follower_feed(self, db_engine):
        """Articles by authors the viewer follows — exclude others."""
        from peerpedia_core.storage.db.crud_article import list_articles
        from peerpedia_core.storage.db.crud_follow import follow_user
        from peerpedia_core.storage.db.models import FollowStorage

        s = get_session(db_engine)
        viewer = _user(id="u-viewer")
        followed = _user(id="u-followed")
        stranger = _user(id="u-stranger")
        s.add_all([viewer, followed, stranger])
        a1 = ArticleMetaStorage(title="", id="a-vf1", status="published", fork_count=0)
        a2 = ArticleMetaStorage(title="", id="a-vf2", status="published", fork_count=0)
        s.add_all([a1, a2])
        s.flush()
        s.add(ArticleAuthorStorage(article_id="a-vf1", author_id="u-followed", position=0))
        s.add(ArticleAuthorStorage(article_id="a-vf2", author_id="u-stranger", position=0))
        # viewer follows u-followed only
        s.add(FollowStorage(follower_id="u-viewer", followed_id="u-followed"))
        s.commit()

        result = list_articles(s, viewer_id="u-viewer")
        assert [r.id for r in result] == ["a-vf1"]

    def test_viewer_follows_nobody_returns_empty(self, db_engine):
        from peerpedia_core.storage.db.crud_article import list_articles
        s = get_session(db_engine)
        viewer = _user(id="u-vfn")
        author = _user(id="u-vfn-au")
        s.add_all([viewer, author])
        a1 = ArticleMetaStorage(title="", id="a-vfn1", status="published", fork_count=0)
        s.add(a1)
        s.flush()
        s.add(ArticleAuthorStorage(article_id="a-vfn1", author_id="u-vfn-au", position=0))
        s.commit()
        assert list_articles(s, viewer_id="u-viewer") == []

    # ── bookmarked_by ───────────────────────────────────────────────────────

    def test_bookmarked_by(self, db_engine):
        from peerpedia_core.storage.db.crud_article import list_articles
        from peerpedia_core.storage.db.models import BookmarkStorage

        s = get_session(db_engine)
        reader = _user(id="u-bm-reader")
        s.add(reader)
        s.add(ArticleMetaStorage(title="", id="a-bm1", status="published", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-bm2", status="published", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-bm3", status="published", fork_count=0))
        s.flush()
        s.add(BookmarkStorage(user_id="u-bm-reader", article_id="a-bm1"))
        s.add(BookmarkStorage(user_id="u-bm-reader", article_id="a-bm3"))
        s.commit()
        result = list_articles(s, bookmarked_by="u-bm-reader")
        assert {r.id for r in result} == {"a-bm1", "a-bm3"}

    def test_bookmarked_by_none_bookmarked_returns_empty(self, db_engine):
        from peerpedia_core.storage.db.crud_article import list_articles
        s = get_session(db_engine)
        reader = _user(id="u-bm-empty")
        s.add(reader)
        s.add(ArticleMetaStorage(title="", id="a-bme1", status="published", fork_count=0))
        s.commit()
        assert list_articles(s, bookmarked_by="u-bm-empty") == []

    # ── ordering ────────────────────────────────────────────────────────────

    def test_ordered_by_created_at_desc(self, db_engine):
        from peerpedia_core.storage.db.crud_article import list_articles
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-ord2", status="draft", fork_count=0))
        s.flush()
        s.add(ArticleMetaStorage(title="", id="a-ord1", status="draft", fork_count=0))
        s.commit()
        # a-ord2 was added first (older created_at), a-ord1 is newer
        result = list_articles(s)
        assert [r.id for r in result] == ["a-ord1", "a-ord2"]

    # ── distinct (no duplicates on JOIN) ────────────────────────────────────

    def test_no_duplicates_when_article_has_multiple_authors(self, db_engine):
        """JOIN with ArticleAuthorStorage must not duplicate rows."""
        from peerpedia_core.storage.db.crud_article import list_articles
        s = get_session(db_engine)
        u1 = _user(id="u-dist1")
        u2 = _user(id="u-dist2")
        s.add_all([u1, u2])
        a = ArticleMetaStorage(title="", id="a-dist", status="draft", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthorStorage(article_id="a-dist", author_id="u-dist1", position=0))
        s.add(ArticleAuthorStorage(article_id="a-dist", author_id="u-dist2", position=1))
        s.commit()
        # Filter by both authors → still one row
        result = list_articles(s, author_ids={"u-dist1", "u-dist2"})
        assert len(result) == 1
        assert result[0].id == "a-dist"

    # ── limit / offset ──────────────────────────────────────────────────────

    def test_respects_limit_and_offset(self, db_engine):
        s = get_session(db_engine)
        for i in range(5):
            s.add(ArticleMetaStorage(title="", id=f"a-lmo{i}", status="published", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        result = list_articles(s, statuses={"published"}, limit=2, offset=1)
        assert len(result) == 2

    def test_limit_zero_returns_empty(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-lz", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        assert list_articles(s, limit=0) == []

    # ── no-match edge cases ─────────────────────────────────────────────────

    def test_returns_empty_when_no_match(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-lm-empty", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import list_articles
        assert list_articles(s, statuses={"published"}) == []

    def test_empty_database_returns_empty(self, db_engine):
        s = get_session(db_engine)
        from peerpedia_core.storage.db.crud_article import list_articles
        assert list_articles(s) == []


class TestCountArticles:
    def test_counts_matching_statuses(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-cm1", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-cm2", status="published", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import count_articles
        assert count_articles(s, statuses={"published"}) == 1

    def test_counts_with_author_filter(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-cm-auth")
        s.add(u)
        s.add(ArticleMetaStorage(title="", id="a-cm3", status="published", fork_count=0))
        s.flush()
        s.add(ArticleAuthorStorage(article_id="a-cm3", author_id="u-cm-auth", position=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import count_articles
        assert count_articles(s, statuses={"published"}, author_id="u-cm-auth") == 1

    def test_empty_status_set_counts_all(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-cm4", status="draft", fork_count=0))
        s.add(ArticleMetaStorage(title="", id="a-cm5", status="published", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import count_articles
        assert count_articles(s, statuses=set()) == 2

    def test_returns_zero_when_no_match(self, db_engine):
        s = get_session(db_engine)
        s.add(ArticleMetaStorage(title="", id="a-cm6", status="draft", fork_count=0))
        s.commit()
        from peerpedia_core.storage.db.crud_article import count_articles
        assert count_articles(s, statuses={"published"}) == 0
