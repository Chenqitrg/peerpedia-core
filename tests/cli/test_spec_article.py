# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Article lifecycle.

LOCKED.  These tests define user-observable CLI behavior.
They must fail when the product breaks — no accommodating bugs.
"""

from __future__ import annotations

import re
import uuid
from argparse import Namespace

import pytest

from peerpedia_core.cli.cmds.account import _cmd_account_register
from peerpedia_core.cli.cmds.article import (
    _cmd_article_create,
    _cmd_article_show,
    _cmd_article_list,
    _cmd_article_edit,
    _cmd_article_publish,
    _cmd_article_delete,
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


def _create(title: str, **kw) -> str:
    """Create an article and return its full short-ID from output."""
    _cmd_article_create(Namespace(
        title=title, content="Body text.",
        format="markdown", publish=False, scores=None,
        no_editor=False, json=False, **kw,
    ))


# ── Spec: Create ──────────────────────────────────────────────────────────


def test_create_prints_title(capsys):
    """``peerpedia article create --title <T>`` prints the title."""
    _ensure_db()
    title = f"On Gravity {_uid()}"
    _register(f"Author-{_uid()}")
    _create(title)
    out = capsys.readouterr().out
    assert title in out, f"create output must contain title '{title}', got: {out}"


def test_create_and_publish_immediately(capsys):
    """``--publish`` creates and publishes in one step."""
    _ensure_db()
    title = f"Quick Publish {_uid()}"
    _register(f"Author-{_uid()}")
    _cmd_article_create(Namespace(
        title=title, content="Body.", format="markdown",
        publish=True, scores="orig=5,rigor=4,comp=3,ped=4,imp=5",
        no_editor=False, json=False,
    ))
    out = capsys.readouterr().out
    assert title in out, f"publish output must contain title, got: {out}"


# ── Spec: Show ────────────────────────────────────────────────────────────


def test_show_nonexistent(capsys):
    """Showing a non-existent article prints an error, does not crash."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    capsys.readouterr()

    _cmd_article_show(Namespace(id="nonexistent_xyz", json=False, show="meta"))
    out = capsys.readouterr().out
    assert "not found" in out.lower(), f"non-existent must say not found, got: {out}"


# ── Spec: List ────────────────────────────────────────────────────────────


def test_list_mine_shows_article(capsys):
    """``article list --mine`` shows the user's article."""
    _ensure_db()
    title = f"My Paper {_uid()}"
    _register(f"Author-{_uid()}")
    _create(title)
    capsys.readouterr()

    _cmd_article_list(Namespace(
        search=None, status=None, mine=True, feed=False,
        bookmarked=False, user=None, server=None, json=False,
    ))
    out = capsys.readouterr().out
    assert title in out, f"--mine list must show '{title}', got: {out}"


def test_list_empty_shows_hint(capsys):
    """An empty search prints guidance, does not crash."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    capsys.readouterr()

    _cmd_article_list(Namespace(
        search="zzz_no_match_zzz", status=None, mine=False,
        feed=False, bookmarked=False, user=None, server=None, json=False,
    ))
    out = capsys.readouterr().out
    assert "No articles" in out or "no articles" in out.lower(), \
        f"empty list must guide user, got: {out}"


# ── Spec: Edit ────────────────────────────────────────────────────────────


def test_edit_title(capsys):
    """``article edit <ref> --title <new>`` changes the title."""
    _ensure_db()
    old_title = f"Old Title {_uid()}"
    new_title = f"New Title {_uid()}"
    _register(f"Author-{_uid()}")
    _create(old_title)
    capsys.readouterr()

    _cmd_article_edit(Namespace(
        id=old_title, content=None, title=new_title,
        no_editor=True, json=False,
    ))
    out = capsys.readouterr().out
    assert new_title in out, f"edit output must contain new title, got: {out}"


# ── Spec: Delete ──────────────────────────────────────────────────────────


def test_delete_prints_deleted(capsys):
    """``article delete <ref>`` prints 'deleted'."""
    _ensure_db()
    title = f"To Delete {_uid()}"
    _register(f"Author-{_uid()}")
    _create(title)
    capsys.readouterr()

    _cmd_article_delete(Namespace(id=title, json=False))
    out = capsys.readouterr().out
    assert "deleted" in out.lower(), f"delete output must say deleted, got: {out}"


# ── Spec: Publish ─────────────────────────────────────────────────────────


def test_publish_prints_status(capsys):
    """``article publish <ref> --scores ...`` prints published/sedimentation."""
    _ensure_db()
    title = f"To Publish {_uid()}"
    _register(f"Author-{_uid()}")
    _create(title)
    capsys.readouterr()

    _cmd_article_publish(Namespace(
        id=title, scores="orig=3,rigor=3,comp=3,ped=3,imp=3", json=False,
    ))
    out = capsys.readouterr().out
    assert "published" in out.lower() or "sedimentation" in out.lower(), \
        f"publish must show status, got: {out}"
