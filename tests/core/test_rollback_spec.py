# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Rollback — revert to a previous commit.

STATUS: LOCKED — these define product behavior.
"""

from tests.core.conftest import make_signing_key, make_user


def _article(db, author):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title="Rollback Test", content="v1",
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


class TestRollbackWorkflow:
    def test_rollback_restores_previous_content(self, db, articles_dir):
        """Edit an article, then rollback to the initial commit."""
        from peerpedia_core.core import rollback_article, update_article_content
        from peerpedia_core.storage.git import get_commit_history, read_article_source
        from peerpedia_core.config.paths import article_repo_path

        author = make_user(db, "Author")
        a = _article(db, author)
        rp = article_repo_path(a["id"])

        # Get the content commit hash (before any edits)
        history = get_commit_history(rp)
        target_hash = history[0]["hash"]  # the "v1" content commit

        # Edit the article
        key, pubkey = make_signing_key("author@peerpedia")
        update_article_content(
            db, a["id"], content="v2 — bad edit", message="bad edit", user_id=author.id,
            signing_key_bytes=key, pubkey_hex=pubkey,
        )

        # Rollback to the v1 commit
        rollback_article(db, a["id"], target_hash, user_id=author.id,
                         signing_key_bytes=key, pubkey_hex=pubkey)

        content, _ = read_article_source(rp)
        assert "v1" in content
        assert "bad edit" not in content
