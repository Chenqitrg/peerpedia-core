# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for ScriptMaintainer CRUD and command orchestration."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.exceptions import ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.storage.db.crud_article import create_article, delete_article, get_article
from peerpedia_core.storage.db.crud_maintainer import (
    add_maintainer,
    remove_maintainer,
    get_maintainer_ids,
    is_maintainer,
)
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, User
from peerpedia_core.commands.maintainers import (
    add_maintainer_to_article,
    remove_maintainer_from_article,
    list_maintainers,
)


def _user(db: Session, user_id: str, name: str | None = None) -> User:
    u = User(id=user_id, name=name or user_id)
    db.add(u)
    db.flush()
    return u


def _article(db: Session, article_id: str, authors: list[str], status: str = "draft") -> Article:
    a = create_article(db, id=article_id, title="Test Article", authors=authors, status=status)
    db.flush()
    return a


# ── CRUD: add_maintainer ─────────────────────────────────────────────────


class TestAddMaintainer:
    def test_adds_row(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        db.commit()

        assert is_maintainer(db, "a1", "u1")

    def test_duplicate_raises_integrity_error(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        db.commit()

        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            add_maintainer(db, "a1", "u1")
            db.flush()


# ── CRUD: remove_maintainer ──────────────────────────────────────────────


class TestRemoveMaintainer:
    def test_removes_row(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        db.commit()

        assert remove_maintainer(db, "a1", "u1") is True
        db.commit()
        assert not is_maintainer(db, "a1", "u1")

    def test_nonexistent_returns_false(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        db.commit()

        assert remove_maintainer(db, "a1", "u1") is False


# ── CRUD: get_maintainer_ids ─────────────────────────────────────────────


class TestGetMaintainerIds:
    def test_returns_ordered_ids(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _user(db, "u2")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        add_maintainer(db, "a1", "u2")
        db.commit()

        ids = get_maintainer_ids(db, "a1")
        assert ids == ["u1", "u2"]  # ordered by created_at

    def test_empty_for_no_maintainers(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        db.commit()

        assert get_maintainer_ids(db, "a1") == []


# ── CRUD: is_maintainer ──────────────────────────────────────────────────


class TestIsMaintainer:
    def test_true_for_maintainer(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        db.commit()

        assert is_maintainer(db, "a1", "u1")

    def test_false_for_non_maintainer(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        db.commit()

        assert not is_maintainer(db, "a1", "u1")


# ── Cascade delete ───────────────────────────────────────────────────────


class TestCascadeDelete:
    def test_article_delete_removes_maintainers(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        db.commit()

        delete_article(db, "a1")
        db.commit()

        assert get_maintainer_ids(db, "a1") == []
        assert get_article(db, "a1") is None


# ── Commands: add_maintainer_to_article ──────────────────────────────────


class TestAddMaintainerCommand:
    def test_maintainer_can_add(self, db_engine):
        db = get_session(db_engine)
        _user(db, "caller")
        _user(db, "new")
        _article(db, "a1", ["caller"])
        add_maintainer(db, "a1", "caller")
        db.commit()

        result = add_maintainer_to_article(db, "a1", "new", "caller")
        db.commit()

        assert result["action"] == "added"
        assert is_maintainer(db, "a1", "new")

    def test_non_maintainer_cannot_add(self, db_engine):
        db = get_session(db_engine)
        _user(db, "caller")
        _user(db, "new")
        _article(db, "a1", ["new"])
        db.commit()

        with pytest.raises(NotAuthorizedError, match="is not a maintainer"):
            add_maintainer_to_article(db, "a1", "new", "caller")

    def test_duplicate_add_raises(self, db_engine):
        db = get_session(db_engine)
        _user(db, "caller")
        _article(db, "a1", ["caller"])
        add_maintainer(db, "a1", "caller")
        db.commit()

        with pytest.raises(ConflictError, match="already a maintainer"):
            add_maintainer_to_article(db, "a1", "caller", "caller")


# ── Commands: remove_maintainer_from_article ─────────────────────────────


class TestRemoveMaintainerCommand:
    def test_maintainer_can_remove(self, db_engine):
        db = get_session(db_engine)
        _user(db, "caller")
        _user(db, "other")
        _article(db, "a1", ["caller"])
        add_maintainer(db, "a1", "caller")
        add_maintainer(db, "a1", "other")
        db.commit()

        result = remove_maintainer_from_article(db, "a1", "other", "caller")
        db.commit()

        assert result["action"] == "removed"
        assert not is_maintainer(db, "a1", "other")

    def test_non_maintainer_cannot_remove(self, db_engine):
        db = get_session(db_engine)
        _user(db, "caller")
        _user(db, "other")
        _article(db, "a1", ["other"])
        add_maintainer(db, "a1", "other")
        db.commit()

        with pytest.raises(NotAuthorizedError, match="is not a maintainer"):
            remove_maintainer_from_article(db, "a1", "other", "caller")

    def test_remove_last_maintainer_allowed(self, db_engine):
        """Transfer pattern: the last maintainer can remove themselves
        after adding a new maintainer (add-before-remove)."""
        db = get_session(db_engine)
        _user(db, "caller")
        _user(db, "new")
        _article(db, "a1", ["caller"])
        add_maintainer(db, "a1", "caller")
        db.commit()

        # Transfer: add new, then remove self
        add_maintainer_to_article(db, "a1", "new", "caller")
        result = remove_maintainer_from_article(db, "a1", "caller", "caller")
        db.commit()

        assert result["action"] == "removed"
        assert is_maintainer(db, "a1", "new")
        assert not is_maintainer(db, "a1", "caller")


# ── Commands: list_maintainers ───────────────────────────────────────────


class TestListMaintainers:
    def test_returns_maintainer_ids(self, db_engine):
        db = get_session(db_engine)
        _user(db, "u1")
        _user(db, "u2")
        _article(db, "a1", ["u1"])
        add_maintainer(db, "a1", "u1")
        add_maintainer(db, "a1", "u2")
        db.commit()

        ids = list_maintainers(db, "a1")
        assert ids == ["u1", "u2"]

    def test_raises_for_nonexistent_article(self, db_engine):
        db = get_session(db_engine)
        with pytest.raises(NotFoundError, match="Article not found"):
            list_maintainers(db, "nonexistent")
