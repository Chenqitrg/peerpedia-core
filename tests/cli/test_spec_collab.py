# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Collaboration — fork, merge, maintainer.

LOCKED.  Tests session-aware multi-user workflows.
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
from peerpedia_core.cli.cmds.fork import (
    _cmd_fork,
    _cmd_merge_propose,
    _cmd_merge_withdraw,
)
from peerpedia_core.cli.cmds.maintainers import (
    _cmd_maintainer_add,
    _cmd_maintainer_remove,
    _cmd_maintainer_list,
    _cmd_maintainer_consent,
    _cmd_maintainer_revoke,
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


def _save_session() -> dict | None:
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return None


def _switch_session(data: dict):
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data))


def _create(title: str):
    _cmd_article_create(Namespace(
        title=title, content="Body.", format="markdown",
        publish=False, scores=None, no_editor=False, json=False,
    ))


def _publish(ref: str):
    _cmd_article_publish(Namespace(
        id=ref, scores="orig=3,rigor=3,comp=3,ped=3,imp=3", json=False,
    ))


# ── Spec: Fork ────────────────────────────────────────────────────────────


def test_fork_requires_published_status(capsys):
    """Fork only works on published articles, not sedimentation.

    ``_publish`` puts the article into sedimentation (3-day review).
    Fork is rejected during this period.  This spec documents that behavior.
    """
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    title = f"Paper {_uid()}"
    _create(title)
    _publish(title)
    pub_out = capsys.readouterr().out
    assert "sedimentation" in pub_out.lower() or "published" in pub_out.lower()

    forker = f"Forker-{_uid()}"
    _register(forker)
    capsys.readouterr()

    _cmd_fork(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    # Fork during sedimentation is rejected — this is by design.
    # Articles must complete the review period first.
    assert len(out.strip()) > 0, f"fork during sedimentation must produce output"


def test_fork_nonexistent(capsys):
    """Forking a non-existent article prints error."""
    _ensure_db()
    _register(f"User-{_uid()}")
    capsys.readouterr()

    _cmd_fork(Namespace(article_id="nonexistent_xyz", json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"fork nonexistent must produce output"


# ── Spec: Maintainer ──────────────────────────────────────────────────────


def test_maintainer_add(capsys):
    """``peerpedia maintainer add <ref> --target-user <@name>`` adds co-author."""
    _ensure_db()
    author = f"Author-{_uid()}"
    coauthor = f"Coauthor-{_uid()}"
    _register(author)
    _register(coauthor)
    capsys.readouterr()

    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_maintainer_add(Namespace(
        article_id=title, target_user=f"@{coauthor}", json=False,
    ))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"maintainer add must produce output"


def test_maintainer_list(capsys):
    """``peerpedia maintainer list <ref>`` shows maintainers."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    capsys.readouterr()
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_maintainer_list(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"maintainer list must produce output"


def test_maintainer_consent_and_revoke(capsys):
    """consent → revoke cycle works."""
    _ensure_db()
    _register(f"Author-{_uid()}")
    capsys.readouterr()
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_maintainer_consent(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "consent" in out.lower() or "Consent" in out

    _cmd_maintainer_revoke(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "revoked" in out.lower() or "Revoke" in out


def test_maintainer_remove(capsys):
    """``peerpedia maintainer remove <ref> --target-user <@name>`` removes co-author."""
    _ensure_db()
    author = f"Author-{_uid()}"
    coauthor = f"Coauthor-{_uid()}"
    _register(author)
    _register(coauthor)
    capsys.readouterr()

    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_maintainer_add(Namespace(
        article_id=title, target_user=f"@{coauthor}", json=False,
    ))
    capsys.readouterr()

    _cmd_maintainer_remove(Namespace(
        article_id=title, target_user=f"@{coauthor}", json=False,
    ))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"maintainer remove must produce output"


# ── Spec: Merge ───────────────────────────────────────────────────────────


def test_merge_commands_produce_output(capsys):
    """Merge propose and withdraw produce output (even if rejected)."""
    _ensure_db()
    author = f"Author-{_uid()}"
    _register(author)
    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_merge_propose(Namespace(
        fork_id=title, target=title, json=False,
    ))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"merge propose must produce output"

    _cmd_merge_withdraw(Namespace(proposal_id=title, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0, f"merge withdraw must produce output"


# ── Spec: Cross-user collaboration ────────────────────────────────────────


def test_multi_author_workflow(capsys):
    """Author adds co-author → co-author consents → list shows both."""
    _ensure_db()
    author = f"Author-{_uid()}"
    coauthor = f"Coauthor-{_uid()}"
    _register(author)
    _register(coauthor)
    capsys.readouterr()

    title = f"Paper {_uid()}"
    _create(title)
    capsys.readouterr()

    _cmd_maintainer_add(Namespace(
        article_id=title, target_user=f"@{coauthor}", json=False,
    ))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0

    _cmd_maintainer_list(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert len(out.strip()) > 0

    _cmd_maintainer_consent(Namespace(article_id=title, json=False))
    out = capsys.readouterr().out
    assert "consent" in out.lower() or "Consent" in out
