# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git write operations — init, commit, delete.

Callers must validate business rules before calling:
- ``require_commit_signing_key`` / ``require_signing_key_for_pubkey``
- ``require_valid_article_status`` (for status markers)
"""

from pathlib import Path

import git

from peerpedia_core.config.git import make_article_gitignore, ssh_sign_env
from peerpedia_core.config.params import PLATFORM_EMAIL
from peerpedia_core.crypto import write_allowed_signers_file
from peerpedia_core.storage.git.read import assert_on_main


# ── Init ───────────────────────────────────────────────────────────────────


def init_article_repo(repo_path: Path) -> Path:
    """Initialize a new git repository for an article."""
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

    Caller must validate signing requirements via
    ``require_commit_signing_key`` and ``require_signing_key_for_pubkey``.
    """
    repo = git.Repo(repo_path)
    assert_on_main(repo)
    repo.git.add(A=True)
    _guard_not_empty(repo, allow_empty=allow_empty)

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
    """Write a platform ``[status]`` marker commit for integrity tracking.

    Caller must validate *status* via ``require_valid_article_status``.
    """
    return commit_article(
        repo_path, f"[status] {status}", "PeerPedia", PLATFORM_EMAIL,
        signing_key=None, pubkey_hex=None, allow_empty=True,
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _guard_not_empty(repo: git.Repo, *, allow_empty: bool) -> None:
    """Raise ValueError if the repo is clean and *allow_empty* is False."""
    if not allow_empty and not repo.is_dirty(untracked_files=True) and repo.head.is_valid():
        raise ValueError("REPO_IS_CLEAN")


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
