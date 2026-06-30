# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Account lifecycle.

LOCKED.  These tests define user-observable CLI behavior.
They must fail when the product breaks — no try/except hiding bugs.
"""

from __future__ import annotations

import uuid
from argparse import Namespace

import pytest

from peerpedia_core.cli.cmds.account import (
    _cmd_account_register,
    _cmd_account_login,
    _cmd_account_whoami,
    _cmd_account_delete,
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


# ── Spec: Register ────────────────────────────────────────────────────────


def test_register_prints_registered_name(capsys):
    """``peerpedia account register --name <name>`` prints the name in output."""
    _ensure_db()
    name = f"Alice-{_uid()}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "secret123")
        _cmd_account_register(Namespace(name=name, json=False))
    out = capsys.readouterr().out
    assert name in out, f"register output must contain '{name}'"


def test_register_duplicate_is_rejected(capsys):
    """Same name twice → second attempt prints 'already exists'."""
    _ensure_db()
    name = f"Bob-{_uid()}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pw1")
        _cmd_account_register(Namespace(name=name, json=False))
    capsys.readouterr()  # consume

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pw2")
        _cmd_account_register(Namespace(name=name, json=False))
    out = capsys.readouterr().out
    assert "already exists" in out.lower(), f"duplicate must be rejected, got: {out}"


# ── Spec: Whoami ──────────────────────────────────────────────────────────


def test_whoami_not_logged_in_shows_error(capsys):
    """``peerpedia account whoami`` with no session prints 'Not logged in'."""
    _ensure_db()
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    _cmd_account_whoami(Namespace(json=False, verbose=False))
    out = capsys.readouterr().out
    assert "Not logged in" in out, f"whoami must say not logged in, got: {out}"


def test_register_then_whoami(capsys):
    """Register → whoami must print the registered name."""
    _ensure_db()
    name = f"Carol-{_uid()}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pw")
        _cmd_account_register(Namespace(name=name, json=False))
    capsys.readouterr()

    _cmd_account_whoami(Namespace(json=False, verbose=False))
    out = capsys.readouterr().out
    assert name in out, f"whoami must show '{name}' after register, got: {out}"


# ── Spec: Login ───────────────────────────────────────────────────────────


def test_login_restores_session(capsys):
    """Register → clear session → login → whoami must show the name."""
    _ensure_db()
    name = f"Dave-{_uid()}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pass")
        _cmd_account_register(Namespace(name=name, json=False))
    capsys.readouterr()

    if SESSION_FILE.exists():
        SESSION_FILE.unlink()

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pass")
        _cmd_account_login(Namespace(name=name, json=False))
    capsys.readouterr()

    _cmd_account_whoami(Namespace(json=False, verbose=False))
    out = capsys.readouterr().out
    assert name in out, f"whoami after login must show '{name}', got: {out}"


# ── Spec: Delete ──────────────────────────────────────────────────────────


def test_delete_without_login(capsys):
    """Delete without session prints guidance, not a crash."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    _ensure_db()
    _cmd_account_delete(Namespace(json=False))
    out = capsys.readouterr().out
    assert "Not logged in" in out or "login" in out.lower(), \
        f"delete without login must guide user, got: {out}"


def test_register_then_delete(capsys):
    """Register → delete must print 'deleted'."""
    _ensure_db()
    name = f"Eve-{_uid()}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pw")
        _cmd_account_register(Namespace(name=name, json=False))
    capsys.readouterr()

    _cmd_account_delete(Namespace(json=False))
    out = capsys.readouterr().out
    assert "deleted" in out.lower(), f"delete must show 'deleted', got: {out}"
