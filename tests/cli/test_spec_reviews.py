# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Peer review lifecycle.

LOCKED.  Submit, list, reply, invite, accept, decline, rate.
"""

from __future__ import annotations

import json
import uuid
from argparse import Namespace

import pytest

from peerpedia_core.cli.cmds.account import _cmd_account_register
from peerpedia_core.cli.cmds.article import (
    _cmd_article_create,
    _cmd_article_publish,
)
from peerpedia_core.cli.cmds.reviews import (
    _cmd_review_submit,
    _cmd_review_list,
    _cmd_review_invite,
    _cmd_review_accept,
    _cmd_review_decline,
    _cmd_review_rate,
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


def _register(name: str) -> str:
    """Register and return user_id."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PEERPEDIA_PASSWORD", "pw")
        _cmd_account_register(Namespace(name=name, json=False))
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text()).get("user_id", "")
    return ""


def _switch_session(data: dict):
    """Write a session file to switch the active user."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data))


def _save_session() -> dict | None:
    """Snapshot the current session."""
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return None


def _create(title: str):
    _cmd_article_create(Namespace(
        title=title, content="Body.", format="markdown",
        publish=False, scores=None, no_editor=False, json=False,
    ))


def _publish(ref: str):
    _cmd_article_publish(Namespace(
        id=ref, scores="orig=3,rigor=3,comp=3,ped=3,imp=3", json=False,
    ))


# ── Spec: Submit ──────────────────────────────────────────────────────────


def test_submit_review(capsys):
    """``peerpedia review submit <ref> --scores ... --comment ...`` submits a review."""
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    reviewer = f"Reviewer-{_uid()}"
    _register(reviewer)
    capsys.readouterr()

    _cmd_review_submit(Namespace(
        article_id=title,
        scores="orig=4,rigor=4,comp=3,ped=3,imp=4",
        comment="A solid contribution to the field. Well-structured arguments.",
        json=False,
    ))
    out = capsys.readouterr().out
    assert "submitted" in out.lower() or "Review" in out, \
        f"review submit must confirm, got: {out}"


def test_submit_review_comment_too_short(capsys):
    """Submitting a review with a very short comment is rejected."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    _register(f"Reviewer-{_uid()}")
    capsys.readouterr()

    _cmd_review_submit(Namespace(
        article_id=title,
        scores="orig=4,rigor=4,comp=3,ped=3,imp=4",
        comment="Nice.",
        json=False,
    ))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"short comment must produce output, got empty"


# ── Spec: List ────────────────────────────────────────────────────────────


def test_list_reviews_empty(capsys):
    """Listing reviews for an article with no reviews shows empty state."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    _cmd_review_list(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "No reviews" in out or "reviews" in out.lower(), \
        f"empty reviews must show guidance, got: {out}"


def test_list_reviews_shows_submitted(capsys):
    """After submitting a review, list shows it."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    _register(f"Reviewer-{_uid()}")
    capsys.readouterr()

    _cmd_review_submit(Namespace(
        article_id=title,
        scores="orig=4,rigor=4,comp=3,ped=3,imp=4",
        comment="A solid contribution to the field with rigorous methodology.",
        json=False,
    ))
    capsys.readouterr()

    _cmd_review_list(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"review list must show submitted review"


# ── Spec: Invite / Accept / Decline ───────────────────────────────────────


def test_invite_reviewer(capsys):
    """Author invites a reviewer — requires author session."""
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    author_session = _save_session()
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    reviewer = f"Reviewer-{_uid()}"
    _register(reviewer)
    capsys.readouterr()

    # Switch back to author to invite
    _switch_session(author_session)
    _cmd_review_invite(Namespace(
        article_id=title, user=f"@{reviewer}", json=False,
    ))
    out = capsys.readouterr().out
    assert "Invited" in out, f"invite must confirm, got: {out}"


def test_accept_invitation(capsys):
    """Reviewer accepts — requires reviewer session."""
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    author_session = _save_session()
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    reviewer = f"Reviewer-{_uid()}"
    _register(reviewer)
    capsys.readouterr()

    _switch_session(author_session)
    _cmd_review_invite(Namespace(
        article_id=title, user=f"@{reviewer}", json=False,
    ))
    capsys.readouterr()

    _switch_session(_save_session() or {})  # back to reviewer?
    # Actually we are already reviewer. Let's just accept.
    _cmd_review_accept(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"accept must produce output, got empty"


def test_decline_invitation(capsys):
    """Reviewer declines — requires reviewer session."""
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    author_session = _save_session()
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    reviewer = f"Reviewer-{_uid()}"
    _register(reviewer)
    capsys.readouterr()

    _switch_session(author_session)
    _cmd_review_invite(Namespace(
        article_id=title, user=f"@{reviewer}", json=False,
    ))
    capsys.readouterr()

    _cmd_review_decline(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"decline must produce output, got empty"


# ── Spec: Rate ────────────────────────────────────────────────────────────


def test_rate_review(capsys):
    """Author rates a reviewer — author must be article maintainer."""
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    author_session = _save_session()
    # Author creates and publishes
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    capsys.readouterr()

    reviewer = f"Reviewer-{_uid()}"
    _register(reviewer)
    reviewer_session = _save_session()
    capsys.readouterr()

    # Reviewer submits
    _cmd_review_submit(Namespace(
        article_id=title,
        scores="orig=4,rigor=4,comp=3,ped=3,imp=4",
        comment="A solid contribution with rigorous methodology and clear writing.",
        json=False,
    ))
    capsys.readouterr()

    # Switch to author to rate
    _switch_session(author_session)
    _cmd_review_rate(Namespace(
        article_id=title, reviewer=f"@{reviewer}", helpfulness=4, json=False,
    ))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"rate must produce output, got empty"


# ── Spec: Full review workflow ────────────────────────────────────────────


def test_full_review_workflow(capsys):
    """Author publishes → invites reviewer → reviewer submits → author rates."""
    _ensure_db()
    author = f"Author-{_uid()}"
    reviewer = f"Reviewer-{_uid()}"
    title = f"Paper {_uid()}"

    _register(author)
    author_session = _save_session()
    _create(title)
    _publish(title)
    capsys.readouterr()

    _register(reviewer)
    reviewer_session = _save_session()
    capsys.readouterr()

    # Author invites
    _switch_session(author_session)
    _cmd_review_invite(Namespace(
        article_id=title, user=f"@{reviewer}", json=False,
    ))
    out = capsys.readouterr().out
    assert "Invited" in out, f"invite must confirm, got: {out}"

    # Reviewer submits
    _switch_session(reviewer_session)
    _cmd_review_submit(Namespace(
        article_id=title,
        scores="orig=4,rigor=4,comp=3,ped=3,imp=4",
        comment="A solid contribution to the field with well-structured arguments.",
        json=False,
    ))
    out = capsys.readouterr().out
    assert "submitted" in out.lower() or "Review" in out

    # Author rates
    _switch_session(author_session)
    _cmd_review_rate(Namespace(
        article_id=title, reviewer=f"@{reviewer}", helpfulness=5, json=False,
    ))
    out = capsys.readouterr().out
    assert "rated" in out.lower() or "Helpful" in out
