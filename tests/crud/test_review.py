# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for ReviewMetaStorage CRUD."""

from peerpedia_core.storage.db.engine import get_session
from tests.crud.conftest import default_scores, make_article, make_user


class TestReviewCRUD:
    def test_upsert_review(self, engine):
        from peerpedia_core.storage.db.crud_review import upsert_review

        session = get_session(engine)
        reviewer = make_user(session, "rv1")
        author = make_user(session, "au1")
        article = make_article(session, authors=[author.id], status="sedimentation")
        r = upsert_review(
            session, article_id=article.id, commit_hash="abc",
            reviewer_id=reviewer.id, scores=default_scores(),
        )
        assert r.id is not None
        assert r.scope == "sedimentation"
        session.close()

    def test_get_reviews_for_article(self, engine):
        from peerpedia_core.storage.db.crud_review import (
            upsert_review, get_reviews_for_article,
        )

        session = get_session(engine)
        rv1 = make_user(session, "rv_a")
        rv2 = make_user(session, "rv_b")
        author = make_user(session, "au_x")
        article = make_article(session, authors=[author.id], status="sedimentation")
        upsert_review(session, article_id=article.id, commit_hash="h1",
                       reviewer_id=rv1.id, scores=default_scores())
        upsert_review(session, article_id=article.id, commit_hash="h2",
                       reviewer_id=rv2.id, scores=default_scores())
        reviews = get_reviews_for_article(session, article.id)
        assert len(reviews) == 2
        session.close()

    def test_review_different_commits_ok(self, engine):
        from peerpedia_core.storage.db.crud_review import upsert_review

        session = get_session(engine)
        rv = make_user(session, "rv_multi")
        author = make_user(session, "au_multi")
        article = make_article(session, authors=[author.id], status="sedimentation")
        r1 = upsert_review(session, article_id=article.id, commit_hash="commit_1",
                           reviewer_id=rv.id, scores=default_scores())
        r2 = upsert_review(session, article_id=article.id, commit_hash="commit_2",
                           reviewer_id=rv.id,
                           scores={"originality": 5, "rigor": 5, "completeness": 5,
                                   "pedagogy": 5, "impact": 5})
        assert r1.id != r2.id
        assert r1.commit_hash == "commit_1"
        assert r2.commit_hash == "commit_2"
        session.close()

    def test_duplicate_same_commit_upserts(self, engine):
        from peerpedia_core.storage.db.crud_review import upsert_review

        session = get_session(engine)
        rv = make_user(session, "rv_dup")
        author = make_user(session, "au_dup")
        article = make_article(session, authors=[author.id], status="sedimentation")
        first = upsert_review(session, article_id=article.id, commit_hash="same_hash",
                              reviewer_id=rv.id, scores=default_scores())
        updated = upsert_review(session, article_id=article.id, commit_hash="same_hash",
                                reviewer_id=rv.id,
                                scores={"originality": 5, "rigor": 5, "completeness": 5,
                                        "pedagogy": 5, "impact": 5})
        assert updated.id == first.id
        assert updated.scores["originality"] == 5
        session.close()

    def test_upsert_review_updates_existing(self, engine):
        from peerpedia_core.storage.db.crud_review import upsert_review

        session = get_session(engine)
        rv = make_user(session, "rv_upsert")
        author = make_user(session, "au_upsert")
        article = make_article(session, authors=[author.id], status="sedimentation")

        r1 = upsert_review(session, article_id=article.id, commit_hash="hash_u",
                           reviewer_id=rv.id,
                           scores={"originality": 1, "rigor": 1, "completeness": 1,
                                   "pedagogy": 1, "impact": 1})
        new_scores = {"originality": 5, "rigor": 5, "completeness": 5,
                      "pedagogy": 5, "impact": 5}
        r2 = upsert_review(session, article_id=article.id, commit_hash="hash_u",
                           reviewer_id=rv.id, scores=new_scores)
        assert r2.id == r1.id
        assert r2.scores["originality"] == 5
        session.close()
