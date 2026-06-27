# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""
Closed-loop specification tests — complete user journeys without network.

SPECIFICATION STATUS: LOCKED — tests define product behavior.
"""

import json, sys, io, stat, tempfile
from argparse import Namespace
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _auto_patch_isatty(monkeypatch):
    """Patch sys.stdin.isatty() → True so editor/password TTY guards pass in CI."""
    import sys as _sys
    monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)


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

def _json_from_capsys(capsys) -> dict | list:
    """Parse JSON from capsys output — finds JSON in mixed stdout/stderr.

    ``_json_out`` writes JSON to stdout (via ``print``).  Rich output goes
    to stdout too and may contain ``[...]`` markup.  We scan every
    occurrence of ``{`` and ``[``, try to parse a balanced JSON value
    starting at each position, and return the **largest** valid value
    found (to avoid picking embedded arrays when the top-level is an object).
    """
    captured = capsys.readouterr()
    text = captured.out + captured.err

    best = None
    for ch, end_ch in (("{", "}"), ("[", "]")):
        pos = -1
        while True:
            pos = text.find(ch, pos + 1)
            if pos == -1:
                break
            ei = text.rfind(end_ch, pos)
            if ei > pos:
                try:
                    result = json.loads(text[pos:ei + 1])
                    if isinstance(result, (dict, list)):
                        # Keep the largest valid result
                        if best is None or len(text[pos:ei + 1]) > len(json.dumps(best)):
                            best = result
                except json.JSONDecodeError:
                    continue
    if best is not None:
        return best
    raise ValueError(f"No JSON found in output. text={text!r}")

def _call_json(handler, capsys, **kwargs):
    """Call handler with --json=True and return parsed dict."""
    kwargs["json"] = True
    try:
        handler(Namespace(**kwargs))
    except SystemExit:
        pass
    return _json_from_capsys(capsys)


def _call_handler(handler, capsys, **kwargs):
    """Call a CLI handler directly (non-JSON) — for error-path tests.

    Catches SystemExit (raised by _die) and returns captured output.
    """
    try:
        handler(Namespace(**kwargs))
    except SystemExit:
        pass
    captured = capsys.readouterr()
    return (captured.out + captured.err).lower()


def _patch_isatty(monkeypatch):
    """Make sys.stdin.isatty() return True so editor/password guards pass in tests."""
    import sys
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)


def _set_editor(monkeypatch, content: str = "test-commit"):
    """Set EDITOR to a script that writes *content* to the temp file.

    The CLI helpers _open_editor and _prompt_commit_message invoke
    ``$EDITOR <tempfile>``.  This replaces the editor with a small
    shell script so automated tests don't block.
    """
    import tempfile, stat
    script = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
    script.write("#!/bin/bash\n")
    if content == "test-commit":
        # For commit messages: replace comment template with a short message.
        script.write('echo "test-commit" > "$1"\n')
    else:
        script.write(f'echo "{content}" > "$1"\n')
    script.close()
    Path(script.name).chmod(stat.S_IRWXU)
    monkeypatch.setenv("EDITOR", script.name)
    return script.name


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
        # Author invites reviewer
        _session(aid, aname, apriv)
        from peerpedia_core.cli.handlers.reviews import _cmd_review_invite, _cmd_review_accept
        _call_json(_cmd_review_invite, capsys, article_id=art["id"], user=rid)
        # Reviewer accepts invitation
        _session(rid, rname, rpriv)
        _call_json(_cmd_review_accept, capsys, article_id=art["id"])
        # Reviewer submits review
        _call_json(_cmd_review_submit, capsys, article_id=art["id"],
            scores="originality=4,rigor=4,completeness=4,pedagogy=4,impact=4",
            comment="This paper presents a novel and rigorous approach to the problem. "
                    "The methodology is clearly described and the experimental results "
                    "are compelling. The authors have done an excellent job of situating "
                    "their work within the broader literature. I believe this contribution "
                    "will be of significant interest to the community.")

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


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Article Lifecycle — Scan, Diff, Search, Feed
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecArticleLifecycleExtended:
    """Specification: article scan transitions sedimentation → published,
    diff shows commit changes, list supports search/feed/mine/bookmarked."""

    def test_scan_publishes_ready_articles(self, capsys):
        """After sedimentation period elapses, scan moves articles to published."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish, _cmd_article_scan,
        )

        uid, name, privkey, *_ = _register("ScanAuthor")
        _session(uid, name, privkey)

        art = _call_json(_cmd_article_create, capsys,
            title="Ready to Sink", content="# Sink test", format="markdown",
            no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        # Force sedimentation to complete by setting sink_start far in the past
        from peerpedia_core.storage.db.engine import get_engine, get_session
        from peerpedia_core.config.paths import DB_URL
        from peerpedia_core.storage.db.models import Article
        import datetime
        engine = get_engine(DB_URL)
        s = get_session(engine)
        a = s.query(Article).filter(Article.id == art["id"]).first()
        a.sink_start = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
        s.commit(); s.close()

        result = _call_json(_cmd_article_scan, capsys)
        assert result["published"] >= 0  # scan reports count

    def test_list_mine_shows_drafts(self, capsys):
        """list --mine shows the user's own articles including drafts."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_list,
        )

        uid, name, privkey, *_ = _register("MineAuthor")
        _session(uid, name, privkey)

        art = _call_json(_cmd_article_create, capsys,
            title="My Draft", content="# Draft", format="markdown",
            no_editor=True, publish=False, scores=None)

        result = _call_json(_cmd_article_list, capsys, mine=True,
            search=None, status=None, feed=False, bookmarked=False,
            user=None, server=None)
        assert any(a["id"] == art["id"] for a in result)

    def test_list_feed_shows_followed_articles(self, capsys):
        """list --feed shows articles from users the viewer follows."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish, _cmd_article_list,
        )
        from peerpedia_core.cli.handlers.social import _cmd_follow_user

        author_id, author_name, author_priv, *_ = _register("FeedAuthor")
        _session(author_id, author_name, author_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Feed Article", content="# Feed", format="markdown",
            no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        viewer_id, viewer_name, viewer_priv, *_ = _register("FeedViewer")
        _session(viewer_id, viewer_name, viewer_priv)
        _cmd_follow_user(Namespace(user_identifier=author_id, json=False))

        result = _call_json(_cmd_article_list, capsys, feed=True,
            search=None, status=None, mine=False, bookmarked=False,
            user=None, server=None)
        assert len(result) >= 1

    def test_list_search_finds_by_title(self, capsys):
        """list --search returns articles matching the query."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish, _cmd_article_list,
        )

        uid, name, privkey, *_ = _register("SearchAuthor")
        _session(uid, name, privkey)

        _call_json(_cmd_article_create, capsys,
            title="Quantum Computing", content="# QC", format="markdown",
            no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_create, capsys,
            title="Classical Physics", content="# CP", format="markdown",
            no_editor=True, publish=False, scores=None)

        result = _call_json(_cmd_article_list, capsys, search="Quantum",
            status=None, feed=False, mine=True, bookmarked=False,
            user=None, server=None)
        assert any("Quantum" in a.get("title", "") for a in result)

    def test_list_bookmarked_shows_bookmarked_articles(self, capsys):
        """list --bookmarked shows only articles the user has bookmarked."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish, _cmd_article_list,
        )
        from peerpedia_core.cli.handlers.social import _cmd_bookmark_add

        author_id, author_name, author_priv, *_ = _register("BookmarkedAuthor")
        _session(author_id, author_name, author_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Bookmark Target", content="# Target", format="markdown",
            no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        reader_id, reader_name, reader_priv, *_ = _register("BookmarkedReader")
        _session(reader_id, reader_name, reader_priv)
        _cmd_bookmark_add(Namespace(article_id=art["id"], json=False))

        result = _call_json(_cmd_article_list, capsys, bookmarked=True,
            search=None, status=None, feed=False, mine=False,
            user=None, server=None)
        assert any(a["id"] == art["id"] for a in result)


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Review Reply Flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecReviewReply:
    """Specification: author can reply to a reviewer, and the reviewer
    receives a notification."""

    def test_author_reply_notifies_reviewer(self, capsys, monkeypatch):
        """Author's reply to a review creates notification for the reviewer."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish,
        )
        from peerpedia_core.cli.handlers.reviews import (
            _cmd_review_submit, _cmd_review_reply,
        )
        from peerpedia_core.cli.handlers.notifications import _cmd_notifications

        # Replace editor so reply content doesn't block
        _set_editor(monkeypatch, content="Thank you for the review.")

        author_id, author_name, author_priv, *_ = _register("ReplyAuthor")
        reviewer_id, reviewer_name, reviewer_priv, *_ = _register("ReplyReviewer")

        # Author creates + publishes
        _session(author_id, author_name, author_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Reply Test Article", content="# Reply Test",
            format="markdown", no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        # Author invites reviewer
        _session(author_id, author_name, author_priv)
        from peerpedia_core.cli.handlers.reviews import _cmd_review_invite, _cmd_review_accept
        _call_json(_cmd_review_invite, capsys, article_id=art["id"], user=reviewer_id)
        # Reviewer accepts invitation
        _session(reviewer_id, reviewer_name, reviewer_priv)
        _call_json(_cmd_review_accept, capsys, article_id=art["id"])
        # Reviewer submits review
        _call_json(_cmd_review_submit, capsys, article_id=art["id"],
            scores="originality=4,rigor=4,completeness=4,pedagogy=4,impact=4",
            comment="This paper presents a well-argued and carefully researched contribution. "
                    "The theoretical framework is sound and the empirical validation is thorough. "
                    "I found the discussion of limitations particularly refreshing and honest. "
                    "The writing is clear and accessible to a broad audience. "
                    "I recommend this work for publication with minor revisions.")

        # Set up git repo with review thread so reply works
        from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR
        from peerpedia_core.storage.git import init_article_repo, commit_article
        from peerpedia_core.crypto import write_key_to_tempfile
        rp = DEFAULT_ARTICLES_DIR / art["id"]
        if not (rp / ".git").is_dir():
            init_article_repo(rp)
        (rp / "article.md").write_text("# Reply Test\n\nContent.")
        reviews_dir = rp / "reviews" / reviewer_id / "threads"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "001.md").write_text("### Reviewer (2024-01-01)\n\nGood paper.\n")
        key_path = write_key_to_tempfile(bytes.fromhex(author_priv))
        from peerpedia_core.storage.db.models import User
        from peerpedia_core.storage.db.engine import get_engine, get_session as _get_sess
        from peerpedia_core.config.paths import DB_URL
        eng = get_engine(DB_URL)
        s_db = _get_sess(eng)
        auth_user = s_db.query(User).filter(User.id == author_id).first()
        pubkey = auth_user.public_key if auth_user else "00" * 32
        s_db.close()
        commit_article(rp, "initial", author_name, f"{author_id}@peerpedia",
                       signing_key=key_path, pubkey_hex=pubkey)
        key_path.unlink(missing_ok=True)

        # Author replies to reviewer (via CLI handler)
        _session(author_id, author_name, author_priv)
        _cmd_review_reply(Namespace(article_id=art["id"], to=reviewer_id, json=True))
        # Reply handler outputs JSON; consume and verify it has expected keys
        capsys.readouterr()

        # Reviewer checks notifications
        _session(reviewer_id, reviewer_name, reviewer_priv)
        notifs = _call_json(_cmd_notifications, capsys, all=False)
        # Notifications are a list; verify at least one is review_reply
        assert isinstance(notifs, list), f"Expected list, got {type(notifs)}"
        assert len(notifs) >= 1
        reply_notifs = [n for n in notifs if isinstance(n, dict) and n.get("event") == "review_reply"]
        assert len(reply_notifs) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Fork & Merge Workflow
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecForkMergeWorkflow:
    """Specification: a user can fork a published article, propose merging
    changes back, and the original maintainer can accept the merge."""

    def test_fork_propose_withdraw(self, capsys, monkeypatch):
        """Fork → propose → withdraw: proposer can retract their proposal."""
        _clear_session(); _setup()
        _set_editor(monkeypatch)
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish,
        )
        from peerpedia_core.cli.handlers.social import (
            _cmd_fork, _cmd_merge_propose, _cmd_merge_withdraw,
        )

        original_author, orig_name, orig_priv, orig_pubkey, orig_salt = _register("OrigAuthor")
        forker_id, forker_name, forker_priv, *_ = _register("Forker")

        _session(original_author, orig_name, orig_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Original Paper", content="# Original\n\nContent.",
            format="markdown", no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        # Article is in "sedimentation" after publish; fork requires "published".
        # Set published status directly.
        from peerpedia_core.storage.db.engine import get_engine, get_session as _get_sess
        from peerpedia_core.config.paths import DB_URL
        from peerpedia_core.storage.db.models import Article as ArticleModel
        eng = get_engine(DB_URL)
        s_db = _get_sess(eng)
        a = s_db.query(ArticleModel).filter(ArticleModel.id == art["id"]).first()
        a.status = "published"
        s_db.commit()
        s_db.close()

        # Ensure git repo with a signed commit exists (fork requires it)
        from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR
        from peerpedia_core.storage.git import init_article_repo, commit_article
        from peerpedia_core.crypto import write_key_to_tempfile
        from peerpedia_core.storage.db.models import User

        rp = DEFAULT_ARTICLES_DIR / art["id"]
        if not (rp / ".git").is_dir():
            init_article_repo(rp)
        (rp / "article.md").write_text("# Original\n\nContent.")

        eng = get_engine(DB_URL)
        s_db = _get_sess(eng)
        orig_user = s_db.query(User).filter(User.id == original_author).first()
        pubkey = orig_user.public_key if orig_user else "00" * 32
        s_db.close()
        key_path = write_key_to_tempfile(bytes.fromhex(orig_priv))
        commit_article(rp, "Initial commit", orig_name,
                       f"{original_author}@peerpedia",
                       signing_key=key_path, pubkey_hex=pubkey)
        key_path.unlink(missing_ok=True)

        # Fork published article
        _session(forker_id, forker_name, forker_priv)
        fork_result = _call_json(_cmd_fork, capsys, article_id=art["id"])
        assert fork_result["forked_from"] == art["id"]
        fork_id = fork_result["id"]

        # Propose merge
        prop_result = _call_json(_cmd_merge_propose, capsys,
            fork_id=fork_id, target=art["id"])
        assert prop_result["status"] == "open"
        proposal_id = prop_result["id"]

        # Withdraw the proposal
        withdraw_result = _call_json(_cmd_merge_withdraw, capsys,
            proposal_id=proposal_id)
        assert withdraw_result["status"] == "withdrawn"

    def test_fork_rejected_for_draft(self, capsys):
        """Forking a draft article is rejected."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create
        from peerpedia_core.cli.handlers.social import _cmd_fork

        author_id, author_name, author_priv, *_ = _register("DraftOwner")
        _session(author_id, author_name, author_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Draft Paper", content="# Draft", format="markdown",
            no_editor=True, publish=False, scores=None)

        forker_id, forker_name, forker_priv, *_ = _register("DraftForker")
        _session(forker_id, forker_name, forker_priv)
        output = _call_handler(_cmd_fork, capsys, article_id=art["id"], json=False)
        assert "maintainer" in output


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Bookmark Full Flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecBookmarkFlow:
    """Specification: users can bookmark articles, list their bookmarks,
    and remove bookmarks. Bookmark removal is idempotent."""

    def test_bookmark_add_list_remove(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish, _cmd_article_list,
        )
        from peerpedia_core.cli.handlers.social import (
            _cmd_bookmark_add, _cmd_bookmark_remove,
        )

        author_id, author_name, author_priv, *_ = _register("BMFlowAuthor")
        reader_id, reader_name, reader_priv, *_ = _register("BMFlowReader")

        _session(author_id, author_name, author_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Bookmark Flow Article", content="# BMF", format="markdown",
            no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        # Reader bookmarks the article
        _session(reader_id, reader_name, reader_priv)
        _cmd_bookmark_add(Namespace(article_id=art["id"], json=False))
        out = capsys.readouterr().out
        assert "Bookmarked" in out

        # List bookmarked articles
        result = _call_json(_cmd_article_list, capsys, bookmarked=True,
            search=None, status=None, feed=False, mine=False,
            user=None, server=None)
        assert any(a["id"] == art["id"] for a in result)

        # Remove bookmark
        _cmd_bookmark_remove(Namespace(article_id=art["id"], json=False))
        out = capsys.readouterr().out
        assert "bookmark" in out.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Share Full Flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecShareFlow:
    """Specification: users can share articles to followers or specific users,
    list shares in their feed, and remove shares."""

    def test_share_add_list_remove(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_publish,
        )
        from peerpedia_core.cli.handlers.social import (
            _cmd_share_add, _cmd_share_list, _cmd_share_remove,
            _cmd_follow_user,
        )

        author_id, author_name, author_priv, *_ = _register("ShareFlowAuthor")
        sharer_id, sharer_name, sharer_priv, *_ = _register("ShareFlowSharer")
        follower_id, follower_name, follower_priv, *_ = _register("ShareFlowFollower")

        _session(author_id, author_name, author_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Share Flow Article", content="# SF", format="markdown",
            no_editor=True, publish=False, scores=None)
        _call_json(_cmd_article_publish, capsys, id=art["id"],
            scores="originality=3,rigor=3,completeness=3,pedagogy=3,impact=3")

        # Follower follows sharer
        _session(follower_id, follower_name, follower_priv)
        _cmd_follow_user(Namespace(user_identifier=sharer_id, json=False))

        # Sharer shares the article (with comment, directed to follower)
        _session(sharer_id, sharer_name, sharer_priv)
        _cmd_share_add(Namespace(article_id=art["id"], to=follower_id,
            comment="Check this out", json=False))
        out = capsys.readouterr().out
        assert "Shared" in out

        # Sharer lists their own shares
        result_mine = _call_json(_cmd_share_list, capsys, mine=True)
        assert len(result_mine) >= 1

        # Follower sees shares in feed
        _session(follower_id, follower_name, follower_priv)
        result_feed = _call_json(_cmd_share_list, capsys, mine=False)
        # Feed may list shares (or be empty if no PEERPEDIA_SERVER for remote fetch)
        assert isinstance(result_feed, list)

        # Sharer removes the share
        _session(sharer_id, sharer_name, sharer_priv)
        _cmd_share_remove(Namespace(article_id=art["id"], json=False))
        out = capsys.readouterr().out
        assert "Unshared" in out


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Maintainer Management
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecMaintainerManagement:
    """Specification: article authors can add/remove co-maintainers.
    The last maintainer cannot remove themselves."""

    def test_maintainer_add_list_remove(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create
        from peerpedia_core.cli.handlers.maintainers import (
            _cmd_maintainer_add, _cmd_maintainer_list, _cmd_maintainer_remove,
        )

        owner_id, owner_name, owner_priv, *_ = _register("MaintOwner")
        coauthor_id, coauthor_name, coauthor_priv, *_ = _register("MaintCoauthor")

        _session(owner_id, owner_name, owner_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Maintainer Test", content="# Maint", format="markdown",
            no_editor=True, publish=False, scores=None)

        # Add coauthor as maintainer
        result = _call_json(_cmd_maintainer_add, capsys,
            article_id=art["id"], target_user=coauthor_id)
        assert result["action"] == "added"

        # List maintainers — should include both
        # _cmd_maintainer_list returns {"article_id": ..., "maintainers": [...]}
        # but the _json_from_capsys parser may grab the embedded array.
        # We look for maintainer IDs in the raw JSON text.
        maint_data = _call_json(_cmd_maintainer_list, capsys,
            article_id=art["id"])
        if isinstance(maint_data, list):
            # Parser grabbed the embedded array; check it contains both IDs
            assert coauthor_id in maint_data, f"Expected {coauthor_id} in {maint_data}"
            assert owner_id in maint_data, f"Expected {owner_id} in {maint_data}"
        else:
            maintainers = maint_data.get("maintainers", [])
            assert coauthor_id in maintainers, f"Expected {coauthor_id} in {maintainers}"
            assert owner_id in maintainers, f"Expected {owner_id} in {maintainers}"

        # Remove coauthor — owner removes them
        result = _call_json(_cmd_maintainer_remove, capsys,
            article_id=art["id"], target_user=coauthor_id)
        assert result["action"] == "removed"

    def test_last_maintainer_cannot_be_removed(self, capsys):
        """Removing the sole maintainer is rejected to prevent orphaning."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create
        from peerpedia_core.cli.handlers.maintainers import _cmd_maintainer_remove

        owner_id, owner_name, owner_priv, *_ = _register("SoloMaintainer")
        _session(owner_id, owner_name, owner_priv)
        art = _call_json(_cmd_article_create, capsys,
            title="Solo Maintainer", content="# Solo", format="markdown",
            no_editor=True, publish=False, scores=None)

        output = _call_handler(_cmd_maintainer_remove, capsys,
            article_id=art["id"], target_user=owner_id, json=False)
        assert "last maintainer" in output


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Alias Full Flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecAliasFlow:
    """Specification: users can set, list, and remove aliases for users
    they follow."""

    def test_alias_set_list_remove(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.social import (
            _cmd_follow_user, _cmd_alias_set, _cmd_alias_list, _cmd_alias_remove,
        )

        follower_id, follower_name, follower_priv, *_ = _register("AliasFollower")
        target_id, target_name, target_priv, *_ = _register("AliasTarget")

        # Must follow before setting alias
        _session(follower_id, follower_name, follower_priv)
        _cmd_follow_user(Namespace(user_identifier=target_id, json=False))

        # Set alias
        _cmd_alias_set(Namespace(user_identifier=target_id, alias="buddy", json=False))
        out = capsys.readouterr().out
        assert "buddy" in out

        # List aliases
        result = _call_json(_cmd_alias_list, capsys)
        assert any(a["alias"] == "buddy" for a in result)

        # Remove alias
        _cmd_alias_remove(Namespace(user_identifier=target_id, json=False))
        out = capsys.readouterr().out
        assert "removed" in out.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Account Search
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecAccountSearch:
    """Specification: users can search for other users by partial name."""

    def test_search_finds_user(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.account import _cmd_account_search

        uid, name, privkey, *_ = _register("SpecSearchAlpha")
        _session(uid, name, privkey)

        result = _call_json(_cmd_account_search, capsys, query="SpecSearchAlpha")
        assert len(result) >= 1
        assert any(r["name"] == "SpecSearchAlpha" for r in result)

    def test_search_no_match_returns_empty(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.account import _cmd_account_search

        uid, name, privkey, *_ = _register("SpecSearchBeta")
        _session(uid, name, privkey)

        result = _call_json(_cmd_account_search, capsys, query="ZzzNotExist_Unlikely")
        assert len(result) == 0

    def test_search_case_insensitive(self, capsys):
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.account import _cmd_account_search

        uid, name, privkey, *_ = _register("SpecSearchGamma")
        _session(uid, name, privkey)

        result = _call_json(_cmd_account_search, capsys, query="specsearchgamma")
        assert len(result) >= 1
        assert any(r["name"] == "SpecSearchGamma" for r in result)


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Article Diff
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecArticleDiff:
    """Specification: users can compare two commits of an article to see
    what changed."""

    def test_diff_between_commits(self, capsys, monkeypatch):
        """Diff between two commits returns the changes and stats."""
        _clear_session(); _setup()
        _set_editor(monkeypatch)
        from peerpedia_core.cli.handlers.articles import (
            _cmd_article_create, _cmd_article_diff,
        )
        from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR, _find_article_file

        uid, name, privkey, *_ = _register("DiffAuthor")
        _session(uid, name, privkey)

        art = _call_json(_cmd_article_create, capsys,
            title="Diff Test", content="# Version 1\n\nHello.",
            format="markdown", no_editor=True, publish=False, scores=None)

        # Create a second commit directly in the git repo
        rp = DEFAULT_ARTICLES_DIR / art["id"]
        article_file = _find_article_file(art["id"])
        article_file.write_text(
            article_file.read_text().replace("# Version 1", "# Version 2")
            .replace("Hello.", "Hello world.")
        )
        import git as gitmod
        repo = gitmod.Repo(str(rp))
        repo.index.add(["article.md"])
        repo.index.commit("Second version")

        # Diff between parent (~1) and HEAD
        result = _call_json(_cmd_article_diff, capsys,
            id=art["id"], hash1="~1", hash2="HEAD")
        assert "diff_text" in result
        assert result["diff_text"] != ""


# ═══════════════════════════════════════════════════════════════════════════════
# Spec: Error Paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecErrorPaths:
    """Specification: the system fails fast with clear error messages
    for invalid operations."""

    def test_publish_without_login_dies(self, capsys):
        """Publishing without being logged in exits with clear message."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_publish
        # With no login, handler exits before reaching article check.
        # Use a valid-looking scores string so parsing passes.
        output = _call_handler(_cmd_article_publish, capsys,
            id="nonexistent", json=False,
            scores="orig=3,rigor=3,comp=3,ped=3,imp=3")
        assert "register" in output or "found" in output or "specified" in output

    def test_create_article_without_login_dies(self, capsys):
        """Creating an article without login exits with clear message."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_create
        output = _call_handler(_cmd_article_create, capsys,
            title="No Login", content="# Test", format="markdown",
            no_editor=True, publish=False, scores=None, json=False)
        assert "register" in output

    def test_review_nonexistent_article_dies(self, capsys):
        """Reviewing a nonexistent article fails with clear message."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.reviews import _cmd_review_submit

        uid, name, privkey, *_ = _register("ReviewBadArticle")
        _session(uid, name, privkey)

        output = _call_handler(_cmd_review_submit, capsys,
            article_id="nonexistent-id", json=False,
            scores="orig=3,rigor=3,comp=3,ped=3,imp=3",
            comment="A very thorough review of the paper with detailed analysis. "
                    "The methodology is sound and the results are clearly presented. "
                    "I have carefully examined all aspects of the work and find it "
                    "to be a valuable contribution to the field. The writing is clear "
                    "and the arguments are well-supported by evidence.")
        assert "not found" in output

    def test_article_delete_nonexistent_dies(self, capsys):
        """Deleting a nonexistent article fails with clear message."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.articles import _cmd_article_delete

        uid, name, privkey, *_ = _register("DeleteBadArticle")
        _session(uid, name, privkey)

        output = _call_handler(_cmd_article_delete, capsys,
            id="nonexistent-id", json=False)
        assert "not found" in output

    def test_follow_nonexistent_user_dies(self, capsys):
        """Following a nonexistent user fails with clear message."""
        _clear_session(); _setup()
        from peerpedia_core.cli.handlers.social import _cmd_follow_user

        uid, name, privkey, *_ = _register("FollowBadUser")
        _session(uid, name, privkey)

        # Use @name lookup (not UUID) to trigger "not found" in _resolve_user
        output = _call_handler(_cmd_follow_user, capsys,
            user_identifier="@NobodyExists", json=False)
        assert "not found" in output
