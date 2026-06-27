# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git write operations — init, commit, delete."""

from pathlib import Path

import git

from peerpedia_core.config.git import make_article_gitignore, ssh_sign_env
from peerpedia_core.config.params import PLATFORM_EMAIL
from peerpedia_core.storage.git.guards import (
    assert_on_main, guard_not_empty,
    require_commit_signing_key, require_signing_key_for_pubkey,
    require_valid_article_status,
)
from peerpedia_core.crypto import write_allowed_signers_file


# ── Init ───────────────────────────────────────────────────────────────────


def init_article_repo(repo_path: Path) -> Path:
    """Initialize a new git repository for an article.

    Creates the repo directory, initializes .git/, writes a ``.gitignore``
    that only allows approved paths (from ``config/git.py``), and creates
    an initial commit with the ``.gitignore``.  Returns repo_path.
    """
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(repo_path, initial_branch="main")
    (repo_path / "reviews").mkdir(exist_ok=True)
    (repo_path / ".gitignore").write_text(make_article_gitignore())
    if not repo.head.is_valid():
        repo.git.add(A=True)
        repo.git.commit(m="Init article repo")
    return repo_path


def is_repo_dirty(repo_path: Path) -> bool:
    """Return True if the git repo at *repo_path* has uncommitted changes."""
    return git.Repo(repo_path).is_dirty(untracked_files=True)


# ── Commit ─────────────────────────────────────────────────────────────────


def commit_article(
    repo_path: Path,
    message: str,
    author_name: str,
    author_email: str,
    signing_key: Path | None,
    pubkey_hex: str | None,
    *,
    allow_empty: bool = False,
) -> str:
    """Stage all changes and commit. Returns the commit hash.

    Non-platform commits MUST be signed.  Set *allow_empty* for
    semantically-empty commits (e.g. status transitions).
    """
    # ── Pre-flight ──
    repo = git.Repo(repo_path)
    assert_on_main(repo)
    repo.git.add(A=True)
    guard_not_empty(repo, allow_empty=allow_empty)

    # ── Signing validation ──
    require_commit_signing_key(signing_key, pubkey_hex, author_email)
    require_signing_key_for_pubkey(signing_key, pubkey_hex)

    # ── Commit ──
    full_message = f"{message}\n\nPubkey: {pubkey_hex}" if pubkey_hex else message
    repo.index.write()
    if signing_key:
        _commit_signed(repo, signing_key, author_email, author_name, full_message)
    else:
        repo.git.commit(
            m=full_message, author=f"{author_name} <{author_email}>", allow_empty=True,
        )
    return repo.head.commit.hexsha


def commit_status_marker(repo_path: Path, status: str) -> str:
    """Write a platform ``[status]`` marker commit for integrity tracking."""
    require_valid_article_status(status)
    return commit_article(
        repo_path, f"[status] {status}", "PeerPedia", PLATFORM_EMAIL,
        signing_key=None, pubkey_hex=None, allow_empty=True,
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _commit_signed(repo, signing_key, author_email, author_name, full_message) -> None:
    """Execute a signed git commit with SSH key material cleanup."""
    pub_path = signing_key.with_suffix(signing_key.suffix + ".pub")
    allowed_signers = None
    try:
        _write_ssh_pubkey(signing_key, pub_path)
        pubkey_line = pub_path.read_text().strip()
        allowed_signers = write_allowed_signers_file(author_email, pubkey_line)
        repo.git.commit(
            S=True, gpg_sign=str(pub_path), m=full_message,
            author=f"{author_name} <{author_email}>", allow_empty=True,
            env=ssh_sign_env(allowed_signers, pub_path),
        )
    finally:
        pub_path.unlink(missing_ok=True)
        if allowed_signers:
            allowed_signers.unlink(missing_ok=True)


def _write_ssh_pubkey(private_key_path: Path, pub_path: Path) -> None:
    """Derive the SSH public key from a private key file using ssh-keygen."""
    import subprocess

    result = subprocess.run(
        ["ssh-keygen", "-y", "-f", str(private_key_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            f"ssh-keygen failed to derive public key: {result.stderr.strip()}"
        )
    pub_path.write_text(result.stdout.strip())


# ── Delete ─────────────────────────────────────────────────────────────────


def delete_article_repo(repo_path: Path) -> None:
    """Delete the git repository for an article (idempotent).

    Called by orchestration layer AFTER the database record has been deleted.
    """
    import shutil

    if repo_path.exists():
        shutil.rmtree(str(repo_path))
