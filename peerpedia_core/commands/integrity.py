# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article integrity verification — commit signatures and DB/git consistency.

Three entry points (see the plan for details):

* **access** — ``level="light"``: verify the latest human-authored commit's
  Ed25519 signature.  Runs before article read/write operations.
* **sync** — ``level="full"``: light + DB cross-validation against git SOT.
  Runs after ``apply_sync_bundle`` completes reconciliation.
* **publish** — ``level="full"``: verify state consistency before allowing
  a status transition to ``sedimentation`` or ``published``.
"""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.config.params import PLATFORM_EMAIL
from peerpedia_core.crypto import pubkey_hex_to_ssh_line
from peerpedia_core.exceptions import SignatureVerificationError
from peerpedia_core.storage.db import Session
from peerpedia_core.commands.workflow import recompute_article_score
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids, update_article_status
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history, verify_commit_signature
from peerpedia_core.types.status import parse_status_tag


def assert_article_integrity(db: Session, article_id: str, *, level: str = "light") -> None:
    """Verify article integrity at the specified level.

    ``level="light"`` — verify the latest human-authored commit's Ed25519
    signature.  Fast enough to run on every article access.  Raises
    ``SignatureVerificationError`` on failure.

    ``level="full"`` — light check + DB cross-validation (status, score,
    authors against git SOT).  If DB state is inconsistent, auto-repair by
    rebuilding the DB cache from git history.  Runs after sync and before
    publish.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return

    article = get_article(db, article_id)
    if article is None:
        return

    if level == "light":
        _verify_light(rp)
    elif level == "full":
        _verify_light(rp)
        _verify_full(db, article_id, rp)
    else:
        raise ValueError(f"Unknown integrity level: {level}")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _verify_light(repo_path: Path) -> None:
    """Verify the latest human-authored commit's signature."""
    commits = list(get_commit_history(repo_path, max_count=1))
    if not commits:
        return
    commit = commits[0]
    if commit["author_email"] == PLATFORM_EMAIL:
        return

    pubkey_hex = _extract_pubkey_from_message(commit["message"])
    if not pubkey_hex:
        raise SignatureVerificationError(
            f"Local integrity failure: commit {commit['hash'][:8]} "
            f"by {commit['author_email']} has no Pubkey trailer — "
            "the git repo may have been tampered with. "
            "Run 'peerpedia sync pull <article_id>' to repair from a trusted peer."
        )
    ssh_line = pubkey_hex_to_ssh_line(pubkey_hex)
    verify_commit_signature(repo_path, commit["hash"], ssh_line, commit["author_email"])


def _verify_full(db: Session, article_id: str, repo_path: Path) -> None:
    """DB cross-validation: rebuild DB cache from git SOT if inconsistent."""
    article = get_article(db, article_id)
    if article is None:
        return

    expected_status = _read_status_from_git(repo_path)
    if expected_status is not None and article.status != expected_status:
        _repair_from_git(db, article_id, repo_path)
        return

    # Check author list consistency.
    db_authors = set(get_author_ids(db, article_id))
    git_authors = _extract_human_authors_from_git(repo_path)
    if db_authors != git_authors:
        from peerpedia_core.commands.articles import rebuild_article_authors  # noqa: PLC0415
        rebuild_article_authors(db, article_id)


def _repair_from_git(db: Session, article_id: str, repo_path: Path) -> None:
    """Rebuild DB cache for *article_id* from git SOT."""
    from peerpedia_core.commands.articles import rebuild_article_authors  # noqa: PLC0415
    from peerpedia_core.commands.bundle import sync_reviews_from_worktree  # noqa: PLC0415

    rebuild_article_authors(db, article_id)
    _sync_status_from_git(db, article_id, repo_path)
    # G9: sync reviews from git worktree before recomputing scores so
    # reviews that exist in git but not in DB are not silently dropped.
    sync_reviews_from_worktree(db, article_id)
    recompute_article_score(db, article_id)


def _read_status_from_git(repo_path: Path) -> str | None:
    """Read the latest [status] tag from platform commit messages.

    Delegates parsing to ``types.status.parse_status_tag`` — the
    single canonical parser for status markers in git history.
    """
    for commit in get_commit_history(repo_path):
        status = parse_status_tag(commit["message"], commit["author_email"])
        if status is not None:
            return status
    return None


def _sync_status_from_git(db: Session, article_id: str, repo_path: Path) -> None:
    """Update article.status in DB to match the latest git platform commit."""
    status = _read_status_from_git(repo_path)
    if status is not None:
        update_article_status(db, article_id, status)


def _extract_human_authors_from_git(repo_path: Path) -> set[str]:
    """Extract unique human author IDs from git commit history."""
    authors: set[str] = set()
    for commit in get_commit_history(repo_path):
        email = commit["author_email"]
        if email == PLATFORM_EMAIL:
            continue
        user_id = _extract_user_id_from_email(email)
        if user_id:
            authors.add(user_id)
    return authors


def _extract_pubkey_from_message(message: str) -> str | None:
    """Extract ``Pubkey: <hex>`` from a commit message. Returns hex or None."""
    for line in message.splitlines():
        if line.startswith("Pubkey: "):
            candidate = line.split("Pubkey: ", 1)[1].strip()
            if candidate:
                return candidate
    return None


def _extract_user_id_from_email(email: str) -> str:
    """Extract user_id from an email like ``<id>@peerpedia``."""
    return email.split("@")[0]
