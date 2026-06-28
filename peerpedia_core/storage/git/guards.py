# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git-layer guard functions — fail-fast, reference message codes."""

from __future__ import annotations

from pathlib import Path

import git

from peerpedia_core.config.git import ssh_verify_env
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.crypto import pubkey_hex_to_ssh_line, write_allowed_signers_file
from peerpedia_core.exceptions import BadRequestError, NotFoundError, SignatureVerificationError
from peerpedia_core.storage.git.read import assert_on_main, read_review_scores
from peerpedia_core.types.status import VALID_ARTICLE_STATUSES, is_platform_commit


def require_valid_article_status(status: str) -> None:
    """Raise ValueError if *status* is not a known article status."""
    if status not in VALID_ARTICLE_STATUSES:
        raise BadRequestError(code="INVALID_ARTICLE_STATUS")


def require_commit_signing_key(signing_key, pubkey_hex: str | None,
                                author_email: str) -> None:
    """Raise ValueError if a non-platform commit is missing signing material."""
    if not is_platform_commit(author_email) and (signing_key is None or not pubkey_hex):
        raise BadRequestError(code="MISSING_SIGNING_KEY")


def require_signing_key_for_pubkey(signing_key, pubkey_hex: str | None) -> None:
    """Raise ValueError if *pubkey_hex* is provided without *signing_key*."""
    if pubkey_hex and not signing_key:
        raise BadRequestError(code="MISSING_SIGNING_KEY")


def extract_pubkey_from_message(message: str) -> str | None:
    """Extract ``Pubkey: <hex>`` from a commit message. Returns hex or None."""
    for line in message.splitlines():
        if line.startswith("Pubkey: "):
            candidate = line.split("Pubkey: ", 1)[1].strip()
            if candidate:
                return candidate
    return None


def verify_commit_signature(repo_path: Path, commit_hash: str,
                             pubkey_ssh_line: str, author_email: str) -> None:
    """Verify that *commit_hash* has a valid Ed25519 signature."""
    signers_path = write_allowed_signers_file(author_email, pubkey_ssh_line)
    try:
        repo = git.Repo(repo_path)
        try:
            repo.git.verify_commit(commit_hash, env=ssh_verify_env(signers_path))
        except git.GitCommandError:
            raise RuntimeError(code="SIGNATURE_VERIFICATION_FAILED")
    finally:
        signers_path.unlink(missing_ok=True)


def assert_repo_on_main(repo_path: Path) -> None:
    """Open the repo at *repo_path* and assert HEAD is on refs/heads/main."""
    assert_on_main(git.Repo(repo_path))


def require_commit_pubkey_signature(repo_path: Path, commit_hash: str,
                                     message: str, author_email: str) -> str:
    """Verify commit signature and return the pubkey hex."""
    pubkey_hex = extract_pubkey_from_message(message)
    if not pubkey_hex:
        raise SignatureVerificationError(code="MISSING_PUBKEY_TRAILER")
    ssh_line = pubkey_hex_to_ssh_line(pubkey_hex)
    verify_commit_signature(repo_path, commit_hash, ssh_line, author_email)
    return pubkey_hex


def guard_not_empty(repo: git.Repo, *, allow_empty: bool) -> None:
    """Raise ValueError if the repo is clean and *allow_empty* is False."""
    if not allow_empty and not repo.is_dirty(untracked_files=True) and repo.head.is_valid():
        raise ValueError("REPO_IS_CLEAN")


def require_article_repo(article_id: str) -> Path:
    """Return the article repo path or raise NotFoundError."""
    rp = article_repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise NotFoundError(code="ARTICLE_REPO_NOT_FOUND",
                            resource_type="article", resource_id=article_id)
    return rp


def require_review_scores(repo_path: Path, reviewer_dir: str,
                           article_id: str) -> dict[str, float]:
    """Return parsed review scores or raise NotFoundError."""
    scores = read_review_scores(repo_path, reviewer_dir)
    if scores is None:
        raise NotFoundError(code="REVIEW_SCORES_NOT_FOUND",
                            resource_type="review_scores",
                            resource_id=f"{article_id}/reviews/{reviewer_dir}")
    return scores
