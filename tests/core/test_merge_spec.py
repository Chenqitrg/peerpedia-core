# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Fork → Merge workflow.

STATUS: LOCKED — these define product behavior.
"""

from tests.core.conftest import make_signing_key, make_user


def _article(db, author, *, title="Test"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title=title, content="# X",
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# SM1 — Fork → edit → propose merge → accept
# ═══════════════════════════════════════════════════════════════════════════════


class TestMergeWorkflow:
    def test_fork_merge_roundtrip(self, db, articles_dir):
        """Fork an article, edit the fork, propose merge, accept it."""
        from peerpedia_core.core import (
            create_article_with_content, fork_article, get_article,
        )
        from peerpedia_core.core.merge import accept_merge, create_merge_proposal
        from peerpedia_core.core.maintainers import add_maintainer_to_article
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        from peerpedia_core.storage.git import (
            commit_article, get_head_hash, read_article_source,
        )

        author = make_user(db, "Author")
        forker = make_user(db, "Forker")
        key, pubkey = make_signing_key("author@peerpedia")
        key2, pubkey2 = make_signing_key("forker@peerpedia")

        # Create original article
        orig = create_article_with_content(
            db, title="Original", content="# Original\n",
            author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
        )
        db.flush()
        orig_id = orig["id"]

        # Add forker as maintainer so they can fork
        add_maintainer(db, orig_id, forker.id)
        db.flush()

        # Forker forks the article
        fork_result = fork_article(db, orig_id, forker.id)
        fork_id = fork_result["id"]

        # Forker edits their fork
        from peerpedia_core.core import update_article_content
        update_article_content(
            db, fork_id, content="# Forked\n\nImproved version.",
            message="improve", user_id=forker.id,
            signing_key_bytes=key2, pubkey_hex=pubkey2,
        )

        # Propose merge from fork → original
        mp = create_merge_proposal(db, fork_id=fork_id, target_id=orig_id, proposer_id=forker.id)
        assert mp.status == "open"

        # Both maintainers must consent
        from peerpedia_core.core.maintainers import consent_to_publish
        consent_to_publish(db, orig_id, author.id)
        consent_to_publish(db, orig_id, forker.id)

        # Author accepts the merge
        accept_merge(db, orig_id, mp.id, author.id)

        # Original now contains fork's content
        from peerpedia_core.config.paths import article_repo_path
        content, _ = read_article_source(article_repo_path(orig_id))
        assert "Forked" in content

    def test_withdraw_merge_proposal(self, db, articles_dir):
        """A proposer can withdraw their own merge proposal."""
        from peerpedia_core.core import create_article_with_content, fork_article
        from peerpedia_core.core.merge import create_merge_proposal, withdraw_merge_proposal
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        author = make_user(db, "Author")
        forker = make_user(db, "Forker")
        key, pubkey = make_signing_key("author@peerpedia")

        orig = create_article_with_content(
            db, title="Orig", content="# X",
            author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
        )
        db.flush()
        add_maintainer(db, orig["id"], forker.id)
        db.flush()
        fork_result = fork_article(db, orig["id"], forker.id)

        mp = create_merge_proposal(db, fork_id=fork_result["id"],
                                   target_id=orig["id"], proposer_id=forker.id)
        withdraw_merge_proposal(db, mp.id, user_id=forker.id)
        assert mp.status == "withdrawn"
