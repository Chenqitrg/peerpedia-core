# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Reconcile operations — score and reputation computation."""

from tests.core.conftest import make_signing_key, make_user


def _make_article(db, articles_dir, author, *, title="Test", status="draft"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    return create_article_with_content(
        db, title=title, content="# X", author_ids=[author.id],
        signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()


class TestReconcileScore:
    def test_reconcile_score_no_reviews_returns_none(self, db, articles_dir):
        from peerpedia_core.core.reconcile import reconcile_score
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author)
        assert reconcile_score(db, a["id"]) is None

    def test_reconcile_score_with_reviews(self, db, articles_dir):
        from peerpedia_core.core.reconcile import reconcile_score
        from peerpedia_core.storage.db.crud_review import upsert_review
        author = make_user(db, "Author")
        rv1 = make_user(db, "Reviewer1")
        rv2 = make_user(db, "Reviewer2")
        a = _make_article(db, articles_dir, author)

        upsert_review(db, article_id=a["id"], commit_hash="h1", reviewer_id=rv1.id,
                      scores={"originality": 4, "rigor": 3, "completeness": 5, "pedagogy": 4, "impact": 4})
        upsert_review(db, article_id=a["id"], commit_hash="h2", reviewer_id=rv2.id,
                      scores={"originality": 3, "rigor": 4, "completeness": 4, "pedagogy": 3, "impact": 3})

        score = reconcile_score(db, a["id"])
        assert score is not None
        assert "originality" in score


class TestReconcileReputation:
    def test_reconcile_reputation_no_articles(self, db):
        from peerpedia_core.core.reconcile import reconcile_reputation
        u = make_user(db, "Scholar")
        rep = reconcile_reputation(db, u.id)
        assert rep.professionalism == 0.0

    def test_reconcile_all_reputations(self, db):
        from peerpedia_core.core.reconcile import reconcile_all_reputations
        make_user(db, "A")
        make_user(db, "B")
        count = reconcile_all_reputations(db)
        assert count == 2
