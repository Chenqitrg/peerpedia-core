# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""
Closed-loop specification tests — complete user journeys without network.

SPECIFICATION STATUS: LOCKED — tests define product behavior.
"""

import json, sys, io
from argparse import Namespace
import pytest

# ── Helpers ──────────────────────────────────────────────────────────────

def _setup():
    from peerpedia_core.config.paths import DB_PATH
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _session(user_id, name, privkey_hex):
    from peerpedia_core.config.paths import SESSION_FILE
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "user_id": user_id, "name": name, "private_key_hex": privkey_hex,
    }))

def _clear_session():
    from peerpedia_core.config.paths import SESSION_FILE
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()

def _register(name, password="password123"):
    """Register a user and return (user_id, name, privkey_hex, pubkey_hex, salt_hex)."""
    import uuid
    from peerpedia_core.crypto import derive_key_pair, new_salt
    from peerpedia_core.storage.db.engine import get_engine, get_session, init_db, migrate_db
    from peerpedia_core.config.paths import DB_URL
    from peerpedia_core.storage.db.models import User

    engine = get_engine(DB_URL)
    init_db(engine)
    migrate_db(engine)
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

def _json_from_capsys(capsys) -> dict:
    """Parse JSON from capsys output — finds JSON in mixed stdout/stderr."""
    captured = capsys.readouterr()
    text = captured.out + captured.err
    # Find the first JSON object or array in the output
    for start_char, end_char in (("[", "]"), ("{", "}")):
        si = text.find(start_char)
        if si >= 0:
            ei = text.rfind(end_char)
            if ei > si:
                try:
                    return json.loads(text[si:ei + 1])
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"No JSON found in output. text={text!r}")

def _call_json(handler, capsys, **kwargs):
    """Call handler with --json=True and return parsed dict."""
    kwargs["json"] = True
    try:
        handler(Namespace(**kwargs))
    except SystemExit:
        pass
    return _json_from_capsys(capsys)


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Register & Publish
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecRegisterPublish:
    def test_register_creates_session(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.account import _cmd_whoami

        uid, name, privkey, pubkey, salt = _register("Alice")
        _session(uid, name, privkey)

        result = _call_json(_cmd_whoami, capsys, verbose=True)
        assert result["name"] == name
        assert result["public_key"] == pubkey

    def test_create_and_publish_article(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create, _cmd_article_publish

        uid, name, privkey, pubkey, salt = _register("Bob")
        _session(uid, name, privkey)

        result = _call_json(_cmd_article_create, capsys,
            title="My First Paper", content="# Abstract\n\nResearch.",
            format="markdown", no_editor=True, publish=False, scores=None)
        assert "id" in result
        article_id = result["id"]

        result = _call_json(_cmd_article_publish, capsys, id=article_id,
            scores="originality=4,rigor=3,completeness=4,pedagogy=3,impact=4")
        assert result["status"] == "sedimentation"


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Review Cycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecReviewCycle:
    def test_review_notifies_author(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create, _cmd_article_publish
        from peerpedia_core.cli.handlers.reviews import _cmd_review_submit
        from peerpedia_core.cli.handlers.notifications import _cmd_notifications

        aid, aname, apriv, *_ = _register("NotifAuthor")
        _session(aid, aname, apriv)
        art = _call_json(_cmd_article_create, capsys, title="Notify Me",
            content="# Test", format="markdown", no_editor=True,
            publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        rid, rname, rpriv, *_ = _register("NotifReviewer")
        _session(rid, rname, rpriv)
        _call_json(_cmd_review_submit, capsys, article_id=art["id"],
            scores="originality=4,rigor=4,completeness=4,pedagogy=4,impact=4",
            comment="Great work!")

        _session(aid, aname, apriv)
        result = _call_json(_cmd_notifications, capsys, all=False)
        assert len(result) >= 1
        assert result[0]["event"] == "review_submitted"


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Social Graph
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecSocialGraph:
    def test_follow_creates_notification(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.social import _cmd_follow_user
        from peerpedia_core.cli.handlers.notifications import _cmd_notifications

        uid, uname, upriv, *_ = _register("NotifFollower")
        tid, tname, tpriv, *_ = _register("NotifTarget")
        _session(uid, uname, upriv)
        _cmd_follow_user(Namespace(user_identifier=tid, json=False))

        # Target checks notifications
        _session(tid, tname, tpriv)
        result = _call_json(_cmd_notifications, capsys, all=False)
        assert len(result) >= 1
        assert result[0]["event"] == "new_follower"


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Multi-Device Bootstrap
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecMultiDevice:
    def test_export_then_bootstrap(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.account import _cmd_whoami, _cmd_bootstrap, _cmd_recover
        from peerpedia_core.storage.db.engine import get_engine, get_session
        from peerpedia_core.config.paths import DB_URL
        from peerpedia_core.storage.db.models import User

        uid, name, privkey, pubkey, salt = _register("MultiDevUser")
        _session(uid, name, privkey)
        export = _call_json(_cmd_whoami, capsys, verbose=True)
        assert export["user_id"] == uid
        assert export["public_key"] == pubkey

        # Simulate new device: clear session + remove user from DB
        _clear_session()
        engine = get_engine(DB_URL)
        s = get_session(engine)
        s.query(User).filter(User.id == uid).delete()
        s.commit(); s.close()

        # Bootstrap on new device
        _call_json(_cmd_bootstrap, capsys, from_=json.dumps(export), peer=None)

        # Recover key
        import getpass
        orig = getpass.getpass
        getpass.getpass = lambda _: "password123"
        try:
            _call_json(_cmd_recover, capsys, user_id=uid, name=None)
        finally:
            getpass.getpass = orig

        result = _call_json(_cmd_whoami, capsys, verbose=True)
        assert result["user_id"] == uid


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Consent Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecConsentModel:
    def test_unanimous_consent(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create
        from peerpedia_core.cli.handlers.maintainers import _cmd_maintainer_consent
        from peerpedia_core.storage.db.engine import get_engine, get_session
        from peerpedia_core.config.paths import DB_URL
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice_id, alice_name, alice_priv, *_ = _register("AliceCons")
        bob_id, bob_name, bob_priv, *_ = _register("BobCons")

        _session(alice_id, alice_name, alice_priv)
        art = _call_json(_cmd_article_create, capsys, title="Co-authored",
            content="# Team", format="markdown", no_editor=True,
            publish=False, scores=None)

        engine = get_engine(DB_URL)
        s = get_session(engine)
        add_maintainer(s, art["id"], bob_id)
        s.commit(); s.close()

        result = _call_json(_cmd_maintainer_consent, capsys, article_id=art["id"])
        assert result["action"] == "consented"

        _session(bob_id, bob_name, bob_priv)
        result = _call_json(_cmd_maintainer_consent, capsys, article_id=art["id"])
        assert result["action"] == "consented"
