# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for BookmarkStorage CRUD."""

from peerpedia_core.storage.db.engine import get_session
from tests.crud.conftest import make_article, make_user


class TestBookmarkCRUD:
    def test_bookmark_crud(self, engine):
        from peerpedia_core.storage.db.crud_bookmark import (
            add_bookmark, get_bookmarks_for_user, is_bookmarked, remove_bookmark,
        )

        session = get_session(engine)
        user = make_user(session, "reader")
        author = make_user(session, "writer")
        a1 = make_article(session, authors=[author.id])
        a2 = make_article(session, authors=[author.id])
        add_bookmark(session, user.id, a1.id)
        add_bookmark(session, user.id, a2.id)
        assert is_bookmarked(session, user.id, a1.id) is True
        bookmarks = get_bookmarks_for_user(session, user.id)
        assert len(bookmarks) == 2
        remove_bookmark(session, user.id, a1.id)
        assert is_bookmarked(session, user.id, a1.id) is False
        assert len(get_bookmarks_for_user(session, user.id)) == 1
        session.close()
