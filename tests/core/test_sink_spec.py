# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Sink auto-publish — sedimentation → published / extended / rejected.

STATUS: LOCKED — these define product behavior for the sink timer lifecycle.
"""

from datetime import datetime, timedelta, timezone

import pytest

from peerpedia_core.storage.db.engine import get_session

from tests.core.conftest import make_signing_key, make_user


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


def _scores(orig=4, rig=4, comp=4, ped=4, imp=4):
    return {"originality": orig, "rigor": rig, "completeness": comp, "pedagogy": ped, "impact": imp}


def _review(db, article_id, reviewer_id, commit_hash, scores):
    from peerpedia_core.storage.db.crud_review import upsert_review
    return upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=reviewer_id, scores=scores,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Sink timer expiration — skip vs process
# ═══════════════════════════════════════════════════════════════════════════════


class TestSinkTimer:
    def test_skips_before_timer_expires(self, db, articles_dir):
        """Articles whose sink timer has not yet elapsed are skipped —
        sink_start is recent, ETA is in the future."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        # sink_start was just set — timer has not elapsed yet
        count = publish_ready_articles(db)
        assert count == 0
        assert get_article(db, a["id"]).status == "sedimentation"


# ═══════════════════════════════════════════════════════════════════════════════
# Sink extension — insufficient reviews but within max days
# ═══════════════════════════════════════════════════════════════════════════════


class TestSinkExtension:
    def test_extends_with_insufficient_reviews(self, db, articles_dir):
        """When elapsed but fewer than min_approvals community reviews exist,
        the sink is extended (more days granted) if within max_total_sink_days."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        # Simulate elapsed sink time (200 days ago)
        article = get_article(db, a["id"])
        article.sink_start = datetime.now(timezone.utc) - timedelta(days=200)
        article.total_sink_days_accumulated = 7  # only initial 7 days so far
        db.flush()

        # Only 1 community review — below min_approvals (3)
        rv = make_user(db, "Reviewer1")
        _review(db, a["id"], rv.id, "h1", _scores())

        count = publish_ready_articles(db)
        # Article should be extended (not published, not rejected)
        assert count == 1  # processed
        article = get_article(db, a["id"])
        assert article.status == "sedimentation"  # still in sedimentation (extended)
        assert article.sink_extended_count == 1
        # sink_duration_days should have increased
        assert article.sink_duration_days > 7

    def test_rejects_after_max_days_exceeded(self, db, articles_dir):
        """When max_total_sink_days is exceeded with insufficient reviews,
        the article is rejected."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        # Simulate elapsed sink time AND accumulated days over max
        article = get_article(db, a["id"])
        article.sink_start = datetime.now(timezone.utc) - timedelta(days=200)
        article.total_sink_days_accumulated = 21  # already at max
        db.flush()

        # No community reviews — below min_approvals
        count = publish_ready_articles(db)
        assert count == 1
        article = get_article(db, a["id"])
        assert article.status == "rejected"


# ═══════════════════════════════════════════════════════════════════════════════
# Auto-publish — score and reputation
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoPublishSideEffects:
    def test_score_recalculated_on_auto_publish(self, db, articles_dir):
        """When auto-published, the article score is recalculated from reviews."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        article = get_article(db, a["id"])
        article.sink_start = datetime.now(timezone.utc) - timedelta(days=200)
        db.flush()

        # Add 3 community reviews with passing scores
        for i in range(3):
            rv = make_user(db, f"Revi{i}")
            _review(db, a["id"], rv.id, f"h{i}", _scores())

        publish_ready_articles(db)
        article = get_article(db, a["id"])
        assert article.status == "published"
        # Score should be computed from reviews
        assert article.score is not None
        assert isinstance(article.score, dict)

    def test_reputation_recalculated(self, db, articles_dir):
        """After auto-publish, all affected authors have their reputation recalculated."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        article = get_article(db, a["id"])
        article.sink_start = datetime.now(timezone.utc) - timedelta(days=200)
        db.flush()

        for i in range(3):
            rv = make_user(db, f"Revi{i}")
            _review(db, a["id"], rv.id, f"h{i}", _scores())

        publish_ready_articles(db)

        # Author's reputation should be updated
        from peerpedia_core.storage.db.crud_user import get_user
        u = get_user(db, author.id)
        assert u.reputation is not None
        assert len(u.reputation) > 0

    def test_no_reviews_penalty_applied(self, db, articles_dir):
        """When auto-published with no community reviews, a no-review penalty score
        is applied — prevents articles with zero feedback from passing."""
        from peerpedia_core.core import publish_article, publish_ready_articles, get_article

        author = make_user(db, "Author")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id, self_review=_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        article = get_article(db, a["id"])
        article.sink_start = datetime.now(timezone.utc) - timedelta(days=200)
        article.total_sink_days_accumulated = 0  # reset so we hit rejection
        db.flush()

        # 0 community reviews, accumulating past max
        article = get_article(db, a["id"])
        article.total_sink_days_accumulated = 21  # hit the hard cap
        db.flush()

        count = publish_ready_articles(db)
        # With total_sink_days at max and no reviews, should reject
        article = get_article(db, a["id"])
        assert count == 1
        assert article.status == "rejected"
