# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Publish lifecycle — draft → sedimentation → reviews → publish.

STATUS: LOCKED — these define product behavior.
"""

from datetime import datetime, timedelta, timezone

import pytest

from tests.core.conftest import make_signing_key, make_user


def _article(db, author, *, status="draft", **kw):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title=kw.pop("title", "Test"), content="# X",
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
        **kw,
    )
    db.flush()
    return result


def _review(db, article_id, reviewer_id, commit_hash, scores):
    from peerpedia_core.storage.db.crud_review import upsert_review
    return upsert_review(db, article_id=article_id, commit_hash=commit_hash,
                         reviewer_id=reviewer_id, scores=scores)


def _build_scores(orig=4, rig=4, comp=4, ped=4, imp=4):
    return {"originality": orig, "rigor": rig, "completeness": comp, "pedagogy": ped, "impact": imp}


# ═══════════════════════════════════════════════════════════════════════════════
# SP1 — Draft → publish to sedimentation with self-review
# ═══════════════════════════════════════════════════════════════════════════════


class TestPublishToSedimentation:
    def test_publish_draft_enters_sedimentation(self, db, articles_dir):
        """A draft published with a self-review MUST enter sedimentation status."""
        from peerpedia_core.core import publish_article, get_article
        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        result = publish_article(
            db, a["id"], user_id=author.id,
            self_review=_build_scores(),
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        article = get_article(db, a["id"])
        assert article.status == "sedimentation"
        assert article.sink_start is not None

    def test_publish_updates_sink_start(self, db, articles_dir):
        """After publish, the article MUST have a sink_start timestamp."""
        from peerpedia_core.core import publish_article, get_article
        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id,
                        self_review=_build_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)
        article = get_article(db, a["id"])
        assert article.status == "sedimentation"
        assert article.sink_start is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SP2 — Auto-publish after reviews
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoPublish:
    def test_article_with_enough_reviews_auto_publishes(self, db, articles_dir):
        """An article with elapsed sink time and ≥3 passing reviews MUST publish."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article
        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        # Publish draft → sedimentation
        publish_article(db, a["id"], user_id=author.id,
                        self_review=_build_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)
        # Simulate elapsed sink time
        article = get_article(db, a["id"])
        past = datetime.now(timezone.utc) - timedelta(days=200)
        article.sink_start = past
        article.sink_duration_days = 7
        db.flush()

        # Add 3 community reviews with passing scores (≥3.0 avg)
        for i in range(3):
            rv = make_user(db, f"Revi{i}")
            _review(db, a["id"], rv.id, f"h{i}", _build_scores())

        count = publish_ready_articles(db)
        assert count == 1
        assert get_article(db, a["id"]).status == "published"
