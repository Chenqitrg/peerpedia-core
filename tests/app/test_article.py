# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Article commands — simulated user input → AppResult."""

import pytest

from peerpedia_core.exceptions import NotAuthorizedError
from tests.app.conftest import login


# ═══════════════════════════════════════════════════════════════════════════════
# show / list — read operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuth:
    def test_create_requires_login(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.exceptions import NotAuthorizedError
        with pytest.raises(NotAuthorizedError):
            create(ctx, title="X", content="# X")


class TestShow:
    def test_show_public_article(self, ctx, articles_dir):
        """Anyone can view an article — no auth required."""
        from peerpedia_core.app.commands.article import create, show
        alice = login(ctx, "Alice")
        a = create(alice, title="Public", content="# X")
        # Unauthenticated viewer
        shown = show(ctx, article_ref=a.data["id"])
        assert shown.data.title == "Public"

    def test_create_then_show(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, show
        alice = login(ctx, "Alice")

        result = create(alice, title="My Paper", content="# Hello")
        assert result.code == "ARTICLE_CREATED"
        aid = result.data["id"]

        shown = show(alice, article_ref=aid)
        assert shown.data.title == "My Paper"


class TestList:
    def test_list_empty(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import list_articles
        alice = login(ctx, "Alice")
        result = list_articles(alice, mine=True)
        assert result.data["items"] == []

    def test_list_mine(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, list_articles
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")

        create(alice, title="Alice's Paper", content="# A")
        create(bob, title="Bob's Paper", content="# B")

        result = list_articles(alice, mine=True)
        titles = [a.title for a in result.data["items"]]
        assert "Alice's Paper" in titles
        assert "Bob's Paper" not in titles


# ═══════════════════════════════════════════════════════════════════════════════
# create / edit / delete — write operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreate:
    def test_create_returns_article_id(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "Alice")
        result = create(alice, title="Test", content="# X")
        assert result.code == "ARTICLE_CREATED"
        assert "id" in result.data

    def test_create_sets_draft_status(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, show
        alice = login(ctx, "Alice")
        result = create(alice, title="Draft", content="# Draft")
        shown = show(alice, article_ref=result.data["id"])
        assert shown.data.status == "draft"


class TestEdit:
    def test_edit_title(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, edit, show
        alice = login(ctx, "Alice")
        a = create(alice, title="Old Title", content="# X")
        edit(alice, article_ref=a.data["id"], title="New Title",
             message="rename", user_id=alice.current_user_id)
        shown = show(alice, article_ref=a.data["id"])
        assert shown.data.title == "New Title"

    def test_edit_title(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, edit, show
        alice = login(ctx, "Alice")
        a = create(alice, title="Old Title", content="# X")
        edit(alice, article_ref=a.data["id"], title="New Title",
             message="rename", user_id=alice.current_user_id)
        shown = show(alice, article_ref=a.data["id"])
        assert shown.data.title == "New Title"


class TestPublish:
    def test_publish_to_sedimentation(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, publish, show
        alice = login(ctx, "Alice")
        a = create(alice, title="Paper", content="# X")
        r = publish(alice, article_ref=a.data["id"],
                    scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
        assert r.code == "ARTICLE_PUBLISHED"
        assert show(alice, article_ref=a.data["id"]).data.status == "sedimentation"


class TestScan:
    def test_scan_no_ready_articles(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, scan
        alice = login(ctx, "Alice")
        create(alice, title="Draft", content="# X")
        r = scan(alice)
        assert r.code in ("ARTICLE_SCANNED", "ARTICLE_SCANNED_EMPTY")
        assert r.data["published"] == 0


class TestDelete:
    def test_delete_own_article(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, delete, show
        alice = login(ctx, "Alice")
        a = create(alice, title="Ephemeral", content="# Gone")
        result = delete(alice, article_ref=a.data["id"])
        assert result.code == "ARTICLE_DELETED"

        with pytest.raises(Exception):
            show(alice, article_ref=a.data["id"])


class TestDiff:
    def test_diff_with_hashes(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, diff
        from peerpedia_core.storage.git import get_head_hash
        from peerpedia_core.config.paths import article_repo_path
        alice = login(ctx, "Alice")
        a = create(alice, title="Diff Paper", content="# V1")
        head = get_head_hash(article_repo_path(a.data["id"]))
        d = diff(alice, article_ref=a.data["id"], hash1=head, hash2=head)
        assert d.data.diff_text is not None
