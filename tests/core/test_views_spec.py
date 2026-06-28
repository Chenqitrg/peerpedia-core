# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: View/feed queries — read-side aggregation."""

from tests.core.conftest import make_signing_key, make_user


def _make_article(db, articles_dir, author, *, title="Test", status="draft"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    return create_article_with_content(
        db, title=title, content="# X", author_ids=[author.id],
        signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()


class TestViews:
    def test_get_article_view(self, db, articles_dir):
        from peerpedia_core.core.views import get_article_view
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author, title="A Paper")
        view = get_article_view(db, a["id"])
        assert view["title"] == "A Paper"
        assert view["authors"] == [author.id]

    def test_list_article_views(self, db, articles_dir):
        from peerpedia_core.core.views import list_article_views
        author = make_user(db, "Author")
        for i in range(3):
            _make_article(db, articles_dir, author, title=f"Paper {i}")
        views = list_article_views(db, author_id=author.id)
        assert len(views) == 3

    def test_get_user_view(self, db):
        from peerpedia_core.core.views import get_user_view
        u = make_user(db, "ProfileUser")
        view = get_user_view(db, u.id)
        assert view["name"] == "ProfileUser"

    def test_get_following_follower_views(self, db):
        from peerpedia_core.core.views import get_following_views, get_follower_views
        from peerpedia_core.core.users import create_user, follow_user
        alice = create_user(db, name="Alice", public_key="00" * 32)
        bob = create_user(db, name="Bob", public_key="11" * 32)
        follow_user(db, alice.id, bob.id)

        following = get_following_views(db, alice.id)
        assert len(following) == 1
        assert following[0]["name"] == "Bob"

        followers = get_follower_views(db, bob.id)
        assert len(followers) == 1
        assert followers[0]["name"] == "Alice"
