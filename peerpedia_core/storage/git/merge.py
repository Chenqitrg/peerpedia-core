# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git merge operations — fork merge, fetch-head merge, clone, checkout, reset."""

import logging
import os
from pathlib import Path

import git

logger = logging.getLogger(__name__)

from peerpedia_core.config.params import PLATFORM_EMAIL
from peerpedia_core.exceptions import MergeConflictError
from peerpedia_core.storage.git.read import assert_on_main


# ── Merge ──────────────────────────────────────────────────────────────────


def merge_git_repos(target: Path, fork: Path, author_name: str) -> str:
    """Merge fork repo into target repo.

    The DB (``ArticleMetaStorage.forked_from``) owns the fork relationship — remote
    refs in ``.git/refs/remotes/`` are an implementation detail.
    """
    target_repo = git.Repo(target)
    assert_on_main(target_repo)
    remote_name = f"fork-{fork.name}"

    try:
        # ── Setup remote ──
        target_repo.create_remote(remote_name, str(fork))
        target_repo.git.fetch(remote_name)

        # ── Resolve fork ref ──
        fork_ref = _resolve_fork_ref(target_repo, remote_name, fork.name)

        # ── Merge ──
        target_repo.git.merge(
            fork_ref.commit.hexsha,
            message=f"[merge] {fork.name}",
            env=_merge_env(author_name),
        )
        merge_hash = target_repo.head.commit.hexsha
    except git.GitCommandError as e:
        _abort_merge(target_repo)
        raise MergeConflictError(f"Merge conflict: {e}") from e
    finally:
        _cleanup_remote(target_repo, remote_name)

    return merge_hash


def merge_fetch_head(repo_path: Path, *, ff_only: bool = True) -> str:
    """Merge FETCH_HEAD into the current branch. Returns the new HEAD hash."""
    repo = git.Repo(repo_path)
    assert_on_main(repo)
    merge_args = ["FETCH_HEAD", "--ff-only"] if ff_only else ["FETCH_HEAD"]
    try:
        repo.git.merge(*merge_args)
    except git.GitCommandError as e:
        _abort_merge(repo)
        raise MergeConflictError(f"Merge failed: {e}") from e
    return repo.head.commit.hexsha


# ── Helpers ────────────────────────────────────────────────────────────────


def _resolve_fork_ref(target_repo: git.Repo, remote_name: str, fork_name: str):
    """Return the main-branch ref of *remote_name*, or raise MergeConflictError."""
    refs = [r for r in target_repo.remotes[remote_name].refs if r.name.endswith("/main")]
    if not refs:
        raise MergeConflictError(
            f"Fork repo {fork_name} has no main branch — "
            "only single-mainline repos are supported"
        )
    return refs[0]


def _merge_env(author_name: str) -> dict[str, str]:
    """Build env dict for a predictable merge commit author."""
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": PLATFORM_EMAIL,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": PLATFORM_EMAIL,
    }


def _abort_merge(repo: git.Repo) -> None:
    """Best-effort abort an in-progress merge."""
    try:
        repo.git.merge("--abort")
    except git.GitCommandError as e:
        logger.warning("Failed to abort merge: %s", e.stderr.strip())


def _cleanup_remote(repo: git.Repo, remote_name: str) -> None:
    """Best-effort delete a git remote."""
    try:
        repo.delete_remote(repo.remotes[remote_name])
    except (IndexError, AttributeError, git.GitCommandError) as e:
        logger.warning("Failed to clean up remote '%s': %s", remote_name, e)


# ── Clone / Checkout / Reset ───────────────────────────────────────────────


def clone_article_repo(src: Path, dst: Path) -> Path:
    """Clone *src* git repository to *dst*. Returns *dst*."""
    git.Repo.clone_from(str(src), str(dst))
    return dst


def checkout_files(repo_path: Path, commit_hash: str) -> None:
    """Checkout all files from *commit_hash* into the working tree."""
    git.Repo(repo_path).git.checkout(commit_hash, "--", ".")


def reset_to_commit(repo_path: Path, commit_hash: str) -> None:
    """Hard-reset the repo at *repo_path* to *commit_hash*."""
    git.Repo(repo_path).git.reset("--hard", commit_hash)


def rollback_to(repo_path: Path, target_hash: str | None, new_hash: str) -> None:
    """Best-effort reset to *target_hash* after a failed merge.  No-op if None."""
    if target_hash is None:
        return
    try:
        reset_to_commit(repo_path, target_hash)
    except Exception as exc:
        logger.warning(
            "Failed to rollback %s %s → %s: %s",
            repo_path.name, new_hash[:7], target_hash[:7], exc,
        )
