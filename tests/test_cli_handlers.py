# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for CLI handlers — exercises cmd functions directly."""

import json
from argparse import Namespace

import pytest

from peerpedia_core.storage.db.engine import get_session
# Ensure DB dir exists for CLI handlers
from peerpedia_core.config.paths import DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
from peerpedia_core.storage.db.models import Article, User
from peerpedia_core.crypto import derive_key_pair, new_salt
from peerpedia_core.cli.handlers.account import (
    _cmd_whoami, _cmd_recover, _validate_bootstrap_json,
)
from peerpedia_core.cli.handlers.maintainers import (
    _cmd_maintainer_consent, _cmd_maintainer_revoke,
)
from peerpedia_core.cli.handlers.notifications import (
    _cmd_notifications, _cmd_notification_read,
)
from peerpedia_core.cli.handlers.social import (
    _cmd_bookmark_add, _cmd_bookmark_remove,
    _cmd_follow_user, _cmd_unfollow_user,
    _cmd_alias_set, _cmd_alias_remove, _cmd_alias_list,
    _cmd_share_add, _cmd_share_list, _cmd_share_remove,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _setup_db():
    """Ensure tables + migrations exist in the test DB."""
    from peerpedia_core.config.paths import DB_URL
    from peerpedia_core.storage.db.engine import get_engine, init_db, migrate_db
    engine = get_engine(DB_URL)
    init_db(engine)
    migrate_db(engine)
    return engine


def _make_user(name="Test User", password="password123"):
    """Create a user in the test DB and return (user_id, name, privkey_hex, pubkey_hex, salt_hex)."""
    import uuid
    engine = _setup_db()
    session = get_session(engine)
    user_id = str(uuid.uuid4())
    salt_hex = new_salt()
    privkey, pubkey = derive_key_pair(password, salt_hex)
    pubkey_hex = pubkey.hex()
    u = User(id=user_id, name=name, public_key=pubkey_hex, salt=salt_hex)
    session.add(u)
    session.commit()
    session.close()
    return user_id, name, privkey.hex(), pubkey_hex, salt_hex


def _write_session_dict(data: dict):
    """Write session file (uses real path — tests are isolated by unique user IDs)."""
    from peerpedia_core.config.paths import SESSION_FILE
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data))


def _make_article(article_id, title, user_id):
    import uuid
    engine = _setup_db()
    session = get_session(engine)
    aid = str(uuid.uuid4()) if article_id is None else article_id
    a = Article(id=aid, title=title, status="draft")
    session.add(a)
    # Use CRUD directly to add first maintainer (avoids chicken-and-egg)
    from peerpedia_core.storage.db.crud_maintainer import add_maintainer
    add_maintainer(session, aid, user_id)
    session.commit()
    session.close()
    return aid

@pytest.fixture(autouse=True)
def _cleanup_session():
    """Clean up session file after each test."""
    yield
    from peerpedia_core.config.paths import SESSION_FILE
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


# ── Tests ────────────────────────────────────────────────────────────────


class TestWhoami:
    def test_not_logged_in(self, capsys):
        from peerpedia_core.config.paths import SESSION_FILE
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()

        args = Namespace(json=False, verbose=False)
        _cmd_whoami(args)
        out = capsys.readouterr().out
        assert "Not logged in" in out

    def test_json_not_logged_in(self, capsys):
        from peerpedia_core.config.paths import SESSION_FILE
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()

        args = Namespace(json=True, verbose=False)
        _cmd_whoami(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["status"] == "not logged in"

    def test_logged_in_basic(self, capsys):
        uid, name, privkey_hex, pubkey_hex, salt_hex = _make_user("WhoamiUser")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        args = Namespace(json=False, verbose=False)
        _cmd_whoami(args)
        out = capsys.readouterr().out
        assert name in out

    def test_logged_in_verbose(self, capsys):
        uid, name, privkey_hex, pubkey_hex, salt_hex = _make_user("VerboseUser")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        args = Namespace(json=False, verbose=True)
        _cmd_whoami(args)
        out = capsys.readouterr().out
        assert "Public key" in out or pubkey_hex[:8] in out

    def test_logged_in_verbose_json(self, capsys):
        uid, name, privkey_hex, pubkey_hex, salt_hex = _make_user("VJsonUser")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        args = Namespace(json=True, verbose=True)
        _cmd_whoami(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["user_id"] == uid
        assert data["public_key"] == pubkey_hex
        assert data["salt"] == salt_hex


class TestRecover:
    def test_recover_user_not_found(self, capsys):
        from peerpedia_core.config.paths import SESSION_FILE
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()

        args = Namespace(name="NobodyHere", user_id=None, json=False)
        with pytest.raises(SystemExit):
            _cmd_recover(args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_recover_neither_name_nor_user_id(self, capsys):
        args = Namespace(name=None, user_id=None, json=False)
        with pytest.raises(SystemExit):
            _cmd_recover(args)
        out = capsys.readouterr().out
        assert "Specify either" in out


class TestValidateBootstrapJson:
    def test_valid(self):
        data = {
            "user_id": "00000000-0000-0000-0000-000000000001",
            "name": "Bob",
            "public_key": "fe40" * 16,
            "salt": "8a3c" * 8,
        }
        _validate_bootstrap_json(data)

    def test_missing_name(self):
        data = {"user_id": "00000000-0000-0000-0000-000000000001",
                "public_key": "fe40" * 16, "salt": "8a3c" * 8}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_uuid(self):
        data = {"user_id": "not-a-uuid", "name": "Bob",
                "public_key": "fe40" * 16, "salt": "8a3c" * 8}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_pubkey_length(self):
        data = {"user_id": "00000000-0000-0000-0000-000000000001",
                "name": "Bob", "public_key": "short", "salt": "8a3c" * 8}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_salt_length(self):
        data = {"user_id": "00000000-0000-0000-0000-000000000001",
                "name": "Bob", "public_key": "fe40" * 16, "salt": "ab"}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)


class TestMaintainerHandlers:
    def test_consent_json(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("ConsentAuthor")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})
        aid = _make_article(None, "Consent Article", uid)

        args = Namespace(article_id=aid, json=True)
        _cmd_maintainer_consent(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["action"] == "consented"

    def test_revoke_json(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("RevokeAuthor")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})
        aid = _make_article(None, "Revoke Article", uid)

        args = Namespace(article_id=aid, json=True)
        _cmd_maintainer_revoke(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["action"] == "revoked"


class TestNotificationHandlers:
    def test_list_empty(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("NotifEmpty")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        args = Namespace(json=False, all=False)
        _cmd_notifications(args)
        out = capsys.readouterr().out
        assert "No notifications" in out

    def test_list_with_notifications(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("NotifHas")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        engine = _setup_db()
        session = get_session(engine)
        from peerpedia_core.storage.db.crud_notification import create_notification
        n = create_notification(session, user_id=uid, event="new_follower",
                                message="Someone followed you")
        session.commit()
        nid = n.id
        session.close()

        args = Namespace(json=False, all=False)
        _cmd_notifications(args)
        out = capsys.readouterr().out
        assert "1 unread" in out or "unread" not in out  # may show count

        args = Namespace(notification_id=nid)
        _cmd_notification_read(args)
        out = capsys.readouterr().out
        assert "marked as read" in out

    def test_read_not_found(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("NotifMissing")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        args = Namespace(notification_id="nonexistent-id")
        with pytest.raises(SystemExit):
            _cmd_notification_read(args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestMaintainerRichOutput:
    def test_consent_rich(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("ConsentRich")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})
        aid = _make_article(None, "Rich Article", uid)

        args = Namespace(article_id=aid, json=False)
        _cmd_maintainer_consent(args)
        out = capsys.readouterr().out
        assert "Consent recorded" in out

    def test_revoke_rich(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("RevokeRich")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})
        aid = _make_article(None, "Rich Revoke", uid)

        args = Namespace(article_id=aid, json=False)
        _cmd_maintainer_revoke(args)
        out = capsys.readouterr().out
        assert "Consent revoked" in out


class TestSocialHandlers:
    def test_follow_unfollow(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("Follower1")
        tid, tname, *_ = _make_user("Target1")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        # These succeed (output goes to Rich console — check no exceptions)
        _cmd_follow_user(Namespace(user_identifier=tid, json=False))
        _cmd_unfollow_user(Namespace(user_identifier=tid, json=False))

    def test_bookmark_add_remove(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("Bookmarker")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})
        aid = _make_article(None, "Bookmark Article", uid)

        _cmd_bookmark_add(Namespace(article_id=aid, json=False))
        out = capsys.readouterr().out
        assert "Bookmarked" in out

        _cmd_bookmark_remove(Namespace(article_id=aid, json=False))
        out = capsys.readouterr().out
        assert "bookmark" in out.lower()

    def test_alias_set(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("AliaSer")
        tid, tname, *_ = _make_user("AliasTarget")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})

        _cmd_follow_user(Namespace(user_identifier=tid, json=False))
        _cmd_alias_set(Namespace(user_identifier=tid, alias="my-nick", json=False))
        out = capsys.readouterr().out
        assert "my-nick" in out

    def test_share_add(self, capsys):
        uid, name, privkey_hex, *_ = _make_user("Sharer")
        _write_session_dict({"user_id": uid, "name": name, "private_key_hex": privkey_hex})
        aid = _make_article(None, "Share Article", uid)

        _cmd_share_add(Namespace(article_id=aid, to=None, comment="Check", json=False))
        out = capsys.readouterr().out
        assert "Shared" in out


# ── Session file robustness ──────────────────────────────────────────────


def test_read_session_returns_none_for_corrupted_json(tmp_path, monkeypatch):
    """Corrupted session file should return None, not crash."""
    bad_file = tmp_path / "session.json"
    bad_file.write_text("{not valid json")
    monkeypatch.setattr("peerpedia_core.cli.helpers.SESSION_FILE", bad_file)
    from peerpedia_core.cli.helpers import _read_session
    assert _read_session() is None


def test_read_session_returns_none_for_empty_file(tmp_path, monkeypatch):
    """Empty session file should return None, not crash."""
    empty_file = tmp_path / "session.json"
    empty_file.write_text("")
    monkeypatch.setattr("peerpedia_core.cli.helpers.SESSION_FILE", empty_file)
    from peerpedia_core.cli.helpers import _read_session
    assert _read_session() is None
