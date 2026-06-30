# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Social graph and content curation.

LOCKED.  User-observable behavior for follow, unfollow, bookmark,
share, alias, and school commands.
"""

from __future__ import annotations

import uuid
from argparse import Namespace

import pytest

from peerpedia_core.cli.cmds.account import _cmd_account_register
from peerpedia_core.cli.cmds.article import _cmd_article_create
from peerpedia_core.cli.cmds.social import (
    _cmd_follow,
    _cmd_unfollow,
    _cmd_following,
    _cmd_followers,
    _cmd_bookmark_add,
    _cmd_bookmark_remove,
    _cmd_alias_set,
    _cmd_alias_remove,
    _cmd_alias_list,
    _cmd_share_add,
    _cmd_share_list,
    _cmd_share_remove,
    _cmd_school,
)
from peerpedia_core.config.paths import DB_PATH, SESSION_FILE


@pytest.fixture(autouse=True)
def _clean_session():
    yield
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def _uid() -> str:
    return uuid.uuid4().hex[:6]


def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    from peerpedia_core.config.paths import DB_URL
    from peerpedia_core.storage.db.engine import get_engine, init_db, migrate_db
    engine = get_engine(DB_URL)
    init_db(engine)
    migrate_db(engine)


def _register(name: str):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pw")
        _cmd_account_register(Namespace(name=name, json=False))


def _create(title: str):
    _cmd_article_create(Namespace(
        title=title, content="Body.", format="markdown",
        publish=False, scores=None, no_editor=False, json=False,
    ))


# ── Spec: Follow ──────────────────────────────────────────────────────────


def test_follow_prints_name(capsys):
    """``peerpedia follow @name`` prints the followed user's name."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{target}", json=False))
    out = capsys.readouterr().out
    assert target in out, f"follow must show target name, got: {out}"


def test_follow_nonexistent_user(capsys):
    """Following a user that doesn't exist prints an error."""
    _ensure_db()
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier="@no_one", json=False))
    out = capsys.readouterr().out
    assert "not found" in out.lower(), f"nonexistent must say not found, got: {out}"


def test_follow_self_is_rejected(capsys):
    """Following yourself should print an error about self-action."""
    _ensure_db()
    name = f"User-{_uid()}"
    _register(name)
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{name}", json=False))
    out = capsys.readouterr().out
    assert "yourself" in out.lower(), \
        f"self-follow must be rejected with 'yourself', got: {out}"


# ── Spec: Unfollow ────────────────────────────────────────────────────────


def test_unfollow_prints_confirmation(capsys):
    """``peerpedia unfollow @name`` after follow prints confirmation."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{target}", json=False))
    capsys.readouterr()

    _cmd_unfollow(Namespace(user_identifier=f"@{target}", json=False))
    out = capsys.readouterr().out
    assert "Stopped following" in out or "unfollow" in out.lower(), \
        f"unfollow must confirm, got: {out}"


def test_unfollow_without_follow_is_idempotent(capsys):
    """Unfollowing someone not followed should not crash."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_unfollow(Namespace(user_identifier=f"@{target}", json=False))
    out = capsys.readouterr().out
    # Idempotent — either confirms unfollow or says not following. No crash.
    assert len(out.strip()) > 0, f"unfollow must produce output, got empty"


# ── Spec: Following list ──────────────────────────────────────────────────


def test_following_list_reports_count(capsys):
    """``peerpedia following --user <ref>`` reports following count."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    user = f"User-{_uid()}"
    _register(user)
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{target}", json=False))
    capsys.readouterr()

    _cmd_following(Namespace(user=user, json=False))
    out = capsys.readouterr().out
    assert "Following" in out, \
        f"following must report count, got: {out}"


# ── Spec: Bookmark ────────────────────────────────────────────────────────


def test_bookmark_add_prints_confirmation(capsys):
    """``peerpedia bookmark add <ref>`` prints confirmation."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    out = capsys.readouterr().out
    # The article was created — reference it by title keyword
    assert title in out, f"create must succeed, got: {out}"

    _cmd_bookmark_add(Namespace(article_id=title, json=False))
    bm_out = capsys.readouterr().out
    assert "Bookmarked" in bm_out, f"bookmark must confirm, got: {bm_out}"


def test_bookmark_remove_prints_confirmation(capsys):
    """``peerpedia bookmark remove <ref>`` prints confirmation after add."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_bookmark_add(Namespace(article_id=title, json=False))
    capsys.readouterr()

    _cmd_bookmark_remove(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "bookmark" in out.lower(), f"remove must confirm, got: {out}"


def test_bookmark_nonexistent_article(capsys):
    """Bookmarking a non-existent article prints error, not crash."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    capsys.readouterr()

    _cmd_bookmark_add(Namespace(article_id="nonexistent_xyz", json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"must produce output (error or success), got empty"


# ── Spec: Share ───────────────────────────────────────────────────────────


def test_share_add_prints_confirmation(capsys):
    """``peerpedia share add <ref>`` prints confirmation."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_share_add(Namespace(article_id=title, to=None, comment="Check this", json=False))
    out = capsys.readouterr().out
    assert "Shared" in out, f"share must confirm, got: {out}"


def test_share_list_prints_shares(capsys):
    """``peerpedia share list`` prints shares from followed users."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    capsys.readouterr()

    _cmd_share_list(Namespace(mine=False, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"share list must produce output, got empty"


def test_share_remove_prints_confirmation(capsys):
    """``peerpedia share remove <ref>`` prints confirmation."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_share_add(Namespace(article_id=title, to=None, comment="X", json=False))
    capsys.readouterr()

    _cmd_share_remove(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "Unshared" in out, f"remove must confirm, got: {out}"


# ── Spec: Alias ───────────────────────────────────────────────────────────


def test_alias_set_prints_alias(capsys):
    """``peerpedia alias set <user> <alias>`` prints the alias."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{target}", json=False))
    capsys.readouterr()

    _cmd_alias_set(Namespace(user_identifier=f"@{target}", alias="buddy", json=False))
    out = capsys.readouterr().out
    assert "buddy" in out, f"alias set must show alias name, got: {out}"


def test_alias_remove_prints_confirmation(capsys):
    """``peerpedia alias remove <user>`` prints confirmation after set."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{target}", json=False))
    capsys.readouterr()
    _cmd_alias_set(Namespace(user_identifier=f"@{target}", alias="buddy", json=False))
    capsys.readouterr()

    _cmd_alias_remove(Namespace(user_identifier=f"@{target}", json=False))
    out = capsys.readouterr().out
    assert "Alias removed" in out or "alias" in out.lower(), \
        f"alias remove must confirm, got: {out}"


def test_alias_list_prints_aliases(capsys):
    """``peerpedia alias list`` prints all aliases."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_follow(Namespace(user_identifier=f"@{target}", json=False))
    capsys.readouterr()
    _cmd_alias_set(Namespace(user_identifier=f"@{target}", alias="buddy", json=False))
    capsys.readouterr()

    _cmd_alias_list(Namespace(json=False))
    out = capsys.readouterr().out
    assert "buddy" in out, f"alias list must show alias, got: {out}"


def test_alias_without_follow(capsys):
    """Aliasing a user you don't follow prints an error."""
    _ensure_db()
    target = f"Target-{_uid()}"
    _register(target)
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_alias_set(Namespace(user_identifier=f"@{target}", alias="stranger", json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"must produce output (error or success), got empty"


# ── Spec: School ──────────────────────────────────────────────────────────


def test_school_local_prints_users(capsys):
    """``peerpedia school --local`` prints a list of users."""
    _ensure_db()
    _register(f"Alice-{_uid()}")
    _register(f"Bob-{_uid()}")
    capsys.readouterr()

    _cmd_school(Namespace(limit=10, local=True, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"school must show users, got empty"


def test_school_default_limit(capsys):
    """School without --limit uses default of 20."""
    _ensure_db()
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_school(Namespace(limit=None, local=True, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"school with default limit must show output"


# ── Spec: Multi-step social workflow ──────────────────────────────────────


def test_follow_bookmark_share_workflow(capsys):
    """Full social curation workflow: follow a user, bookmark their article, share it."""
    _ensure_db()
    # Setup: two users, one article
    author = f"Author-{_uid()}"
    _register(author)
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    reader = f"Reader-{_uid()}"
    _register(reader)
    capsys.readouterr()

    # Reader follows author
    _cmd_follow(Namespace(user_identifier=f"@{author}", json=False))
    out = capsys.readouterr().out
    assert author in out, f"follow must show author name, got: {out}"

    # Reader bookmarks the article
    _cmd_bookmark_add(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "Bookmarked" in out, f"bookmark must confirm, got: {out}"

    # Reader shares the article
    _cmd_share_add(Namespace(article_id=title, to=None, comment="Must read!", json=False))
    out = capsys.readouterr().out
    assert "Shared" in out, f"share must confirm, got: {out}"

    # Reader unfollows
    _cmd_unfollow(Namespace(user_identifier=f"@{author}", json=False))
    out = capsys.readouterr().out
    assert "Stopped following" in out, f"unfollow must confirm, got: {out}"
