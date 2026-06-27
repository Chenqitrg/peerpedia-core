# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git-layer guard functions — validation + signature verification.

Pure-logic validators that don't need ``git.Repo`` live here alongside
guards that DO need ``git.Repo`` (``assert_on_main``, signature checks).
"""

from __future__ import annotations

from pathlib import Path

import git

from peerpedia_core.config.git import ssh_verify_env
from peerpedia_core.types import short_id
from peerpedia_core.types.status import is_platform_commit, VALID_ARTICLE_STATUSES

from peerpedia_core.crypto import pubkey_hex_to_ssh_line
from peerpedia_core.exceptions import SignatureVerificationError
from peerpedia_core.crypto import write_allowed_signers_file

_EXPECTED_BRANCH = "refs/heads/main"

# ── Article status ─────────────────────────────────────────────────────────


def require_valid_article_status(status: str) -> None:
    """Raise ValueError if *status* is not a known article status."""
    if status not in VALID_ARTICLE_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}, must be one of {sorted(VALID_ARTICLE_STATUSES)}"
        )


# ── Commit signing ─────────────────────────────────────────────────────────


def require_commit_signing_key(
    signing_key, pubkey_hex: str | None, author_email: str,
) -> None:
    """Raise ValueError if a non-platform commit is missing signing material."""
    if not is_platform_commit(author_email) and (signing_key is None or not pubkey_hex):
        raise ValueError(
            "signing_key and pubkey_hex are required for non-platform commits"
        )


def require_signing_key_for_pubkey(
    signing_key, pubkey_hex: str | None,
) -> None:
    """Raise ValueError if *pubkey_hex* is provided without *signing_key*."""
    if pubkey_hex and not signing_key:
        raise ValueError("signing_key is required when pubkey_hex is provided")


def assert_on_main(repo: git.Repo) -> None:
    """Raise RuntimeError if HEAD is not on refs/heads/main.

    Article repos use a single-mainline model — all git operations
    expect HEAD to point to ``refs/heads/main``.  This guard prevents
    silent data corruption when a checkout or branch switch moves
    HEAD to a different ref.

    Returns early (no-op) for empty repos with no commits.
    """
    if not repo.head.is_valid():
        return  # empty repo, no commits yet
    if repo.head.is_detached:
        raise RuntimeError(
            "HEAD is detached — expected refs/heads/main; "
            "article repos use a single-mainline model"
        )
    branch_path = repo.head.reference.path
    if branch_path != _EXPECTED_BRANCH:
        raise RuntimeError(
            f"HEAD is on {branch_path}, expected {_EXPECTED_BRANCH} — "
            "article repos use a single-mainline model"
        )



def extract_pubkey_from_message(message: str) -> str | None:
    """Extract ``Pubkey: <hex>`` from a commit message. Returns hex or None."""
    for line in message.splitlines():
        if line.startswith("Pubkey: "):
            candidate = line.split("Pubkey: ", 1)[1].strip()
            if candidate:
                return candidate
    return None



def verify_commit_signature(
    repo_path: Path,
    commit_hash: str,
    pubkey_ssh_line: str,
    author_email: str,
) -> None:
    """Verify that *commit_hash* has a valid Ed25519 signature from *author_email*.

    *pubkey_ssh_line* must be a full SSH public key line
    (``"ssh-ed25519 AAAAC3NzaC1..."``).

    Raises RuntimeError if verification fails.
    """
    # ── Prepare allowed_signers ────────────────────────────────────────────
    signers_path = write_allowed_signers_file(author_email, pubkey_ssh_line)
    try:
        # ── Verify ─────────────────────────────────────────────────────────
        repo = git.Repo(repo_path)
        try:
            repo.git.verify_commit(
                commit_hash,
                env=ssh_verify_env(signers_path),
            )
        except git.GitCommandError as e:
            raise RuntimeError(
                f"Commit {short_id(commit_hash)} by {author_email} "
                f"signature verification failed: {e.stderr.strip()}"
            ) from e
    finally:
        signers_path.unlink(missing_ok=True)



def assert_repo_on_main(repo_path: Path) -> None:
    """Open the repo at *repo_path* and assert HEAD is on refs/heads/main.

    Path-based convenience wrapper for callers that don't already have
    a ``git.Repo`` object.
    """
    assert_on_main(git.Repo(repo_path))



def require_commit_pubkey_signature(
    repo_path: Path, commit_hash: str, message: str, author_email: str,
) -> str:
    """Verify that *commit_hash* has a valid Ed25519 signature.

    Extracts ``Pubkey: <hex>`` from *message*, raises
    ``SignatureVerificationError`` if the trailer is missing, verifies the
    signature, and returns the pubkey hex.
    """

    pubkey_hex = extract_pubkey_from_message(message)
    if not pubkey_hex:
        raise SignatureVerificationError(
            f"Commit {short_id(commit_hash)} by {author_email} "
            "has no Pubkey trailer — unsigned human commit"
        )
    ssh_line = pubkey_hex_to_ssh_line(pubkey_hex)
    verify_commit_signature(repo_path, commit_hash, ssh_line, author_email)
    return pubkey_hex


# ── Commit guards ──────────────────────────────────────────────────────────


def guard_not_empty(repo, *, allow_empty: bool) -> None:
    """Raise ValueError if the repo is clean and *allow_empty* is False."""
    if not allow_empty and not repo.is_dirty(untracked_files=True) and repo.head.is_valid():
        raise ValueError(
            "nothing to commit — repo is clean; "
            "pass allow_empty=True if intentional (e.g., status transition)"
        )



