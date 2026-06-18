# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for multi-status article listing and counting."""

from peerpedia_core.storage.db.crud_article import (
    count_articles_multi_status,
    list_articles_multi_status,
)
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User


def _user(**kwargs):
    """Create a User with required fields filled in."""
    defaults = {
        "password_hash": "",
        "name": "Test User",
        "anonymous_name": "anon",
        "affiliation": "Test",
    }
    defaults.update(kwargs)
    return User(**defaults)


class TestListArticlesMultiStatus:
    def test_empty_statuses_returns_all(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-lm1", status="draft", fork_count=0))
        s.add(Article(id="a-lm2", status="published", fork_count=0))
        s.commit()

        result = list_articles_multi_status(s, set())
        assert len(result) == 2

    def test_filters_by_single_status(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-lm3", status="draft", fork_count=0))
        s.add(Article(id="a-lm4", status="published", fork_count=0))
        s.commit()

        result = list_articles_multi_status(s, {"published"})
        assert [r.id for r in result] == ["a-lm4"]

    def test_filters_by_multiple_statuses(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-lm5", status="draft", fork_count=0))
        s.add(Article(id="a-lm6", status="sedimentation", fork_count=0))
        s.add(Article(id="a-lm7", status="published", fork_count=0))
        s.commit()

        result = list_articles_multi_status(s, {"draft", "sedimentation"})
        ids = {r.id for r in result}
        assert ids == {"a-lm5", "a-lm6"}

    def test_filters_by_author_id(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-lm-auth", username="lm_author")
        s.add(u)
        s.add(Article(id="a-lm8", status="published", fork_count=0))
        a2 = Article(id="a-lm9", status="published", fork_count=0)
        s.add(a2)
        s.flush()
        s.add(ArticleAuthor(article_id="a-lm9", author_id="u-lm-auth", position=0))
        s.commit()

        result = list_articles_multi_status(s, {"published"}, author_id="u-lm-auth")
        assert [r.id for r in result] == ["a-lm9"]

    def test_respects_limit_and_offset(self, db_engine):
        s = get_session(db_engine)
        for i in range(5):
            s.add(Article(id=f"a-lmo{i}", status="published", fork_count=0))
        s.commit()

        result = list_articles_multi_status(s, {"published"}, limit=2, offset=1)
        assert len(result) == 2

    def test_returns_empty_when_no_match(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-lm-empty", status="draft", fork_count=0))
        s.commit()

        result = list_articles_multi_status(s, {"published"})
        assert result == []


class TestCountArticlesMultiStatus:
    def test_counts_matching_statuses(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-cm1", status="draft", fork_count=0))
        s.add(Article(id="a-cm2", status="published", fork_count=0))
        s.commit()

        assert count_articles_multi_status(s, {"published"}) == 1

    def test_counts_with_author_filter(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-cm-auth", username="cm_author")
        s.add(u)
        s.add(Article(id="a-cm3", status="published", fork_count=0))
        s.flush()
        s.add(ArticleAuthor(article_id="a-cm3", author_id="u-cm-auth", position=0))
        s.commit()

        assert count_articles_multi_status(s, {"published"}, author_id="u-cm-auth") == 1

    def test_empty_statuses_counts_all(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-cm4", status="draft", fork_count=0))
        s.add(Article(id="a-cm5", status="published", fork_count=0))
        s.commit()

        assert count_articles_multi_status(s, set()) == 2

    def test_returns_zero_when_no_match(self, db_engine):
        s = get_session(db_engine)
        s.add(Article(id="a-cm6", status="draft", fork_count=0))
        s.commit()

        assert count_articles_multi_status(s, {"published"}) == 0
