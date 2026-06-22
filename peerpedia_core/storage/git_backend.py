# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Layer 0: Git storage backend for article content and reviews.

Every article is an independent git repository stored under
``~/.peerpedia/articles/<article-id>/``.

Git stores content (article body, review files) — the things that need
version history, diff, and fork/merge.  Metadata (status, scores, fork
count) lives in the database so it can be queried and aggregated.

Pure local git — does not depend on bundle or sync modules.

**Hard constraint**: this module depends only on GitPython + stdlib.
It does NOT import any ``peerpedia_core`` module.  It raises only stdlib
exceptions (ValueError, RuntimeError, FileNotFoundError) or its own
``MergeConflictError``.  The caller translates to domain exceptions.

Functions by category
---------------------
Write (mutate state)
    init_article_repo      Create .git/ + reviews/ directory
    commit_article          Stage all changes → commit → return hash
    merge_git_repos         Merge a fork repo into a target repo
    delete_article_repo     Delete the entire repo directory (idempotent)

Read (inspect state)
    get_commit_history      List recent commits with stats
    get_commit_authors      Extract user IDs from commit author emails
    get_diff_between        Diff two arbitrary commits

Review file reading (non-git — reads worktree files directly)
    list_review_dirs        List directory names under reviews/
    read_review_scores      Parse reviews/{dir}/scores.json → dict

Why read review files from the worktree?
----------------------------------------
Reviews arrive through two paths:

1. Local submission (``commands/reviews.py:submit_review``):
   write_review_to_git() → upsert_review(commit_hash=return_value)
   Both git and DB are updated atomically.

2. Remote sync (``commands/sync.py:apply_sync_bundle``):
   git merge FETCH_HEAD → ... → sync_reviews_from_worktree() → upsert_review()
   The bundle merged new review files into git, but nobody told the DB.
   ``sync_reviews_from_worktree`` closes this gap by reading every scores.json from
   the worktree and upserting into the Review cache.

This is NOT a full git-log traversal — it only reads the current worktree
state.  Full historical review reconstruction from git history is deferred.
"""

from pathlib import Path

import git

from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR


def init_article_repo(repo_path: Path) -> Path:
    """Initialize a new git repository for an article.

    Creates the repo directory, initializes .git/, and sets up the
    reviews/ subdirectory.  Returns repo_path.

    **Do not call this function in isolation.**  An empty repo without
    content and an initial commit is invalid.  This function exists
    only as a building block for ``create_article_with_content``
    (and for tests that need a bare git repo).
    """
    repo_path.mkdir(parents=True, exist_ok=True)
    git.Repo.init(repo_path)
    (repo_path / "reviews").mkdir(exist_ok=True)
    return repo_path


def commit_article(
    repo_path: Path,
    message: str,
    author_name: str,
    author_email: str,
    signing_key: Path | None = None,
    pubkey_hex: str | None = None,
) -> str:
    """Stage all changes and commit. Returns the commit hash.

    If the repo already has a HEAD and nothing changed, returns the
    current HEAD hash without creating a new commit.

    If *signing_key* and *pubkey_hex* are provided, the commit is signed
    via git's SSH signing (``gpg.format=ssh``) and the pubkey is embedded
    in the commit message as ``Pubkey: <hex>``.

    TODO(security): signing is implemented but optional — unsigned commits
    are rejected on sync but pollute local history.  Force signing for all
    non-platform commits once the user base has keys.
    """
    import os

    repo = git.Repo(repo_path)
    repo.git.add(A=True)

    # TODO: silently returning the existing HEAD hides the no-op from the
    # caller.  The caller should decide whether to warn, skip downstream
    # work, or reject.  Options: return (hash, was_new), raise, or let git
    # create the empty commit when --allow-empty was the caller's intent.
    if not repo.is_dirty(untracked_files=True) and repo.head.is_valid():
        return repo.head.commit.hexsha  # type: ignore[union-attr]

    # Fail fast: pubkey requires signing key
    if pubkey_hex and not signing_key:
        raise ValueError(
            "pubkey_hex provided but signing_key is None — "
            "a commit with a Pubkey trailer MUST be signed"
        )

    # Append pubkey to message if provided
    full_message = f"{message}\n\nPubkey: {pubkey_hex}" if pubkey_hex else message

    # Write index (git.commit() does not auto-write; index.commit() does)
    repo.index.write()

    # Build commit kwargs
    if signing_key:
        pub_path = signing_key.with_suffix(signing_key.suffix + ".pub")
        _write_ssh_pubkey(signing_key, pub_path)
        allowed_signers = _write_allowed_signers(author_email, pub_path)
        try:
            # Use GIT_CONFIG_COUNT env vars instead of -c flags so the
            # config is applied BEFORE the subcommand — git >= 2.44 rejects
            # -c after 'commit' (it also means --reedit-message there).
            sign_env = {
                **os.environ,
                "GIT_CONFIG_COUNT": "3",
                "GIT_CONFIG_KEY_0": "gpg.format",
                "GIT_CONFIG_VALUE_0": "ssh",
                "GIT_CONFIG_KEY_1": "gpg.ssh.allowedSignersFile",
                "GIT_CONFIG_VALUE_1": str(allowed_signers),
                "GIT_CONFIG_KEY_2": "user.signingkey",
                "GIT_CONFIG_VALUE_2": str(pub_path),
            }
            repo.git.commit(
                S=True,
                gpg_sign=str(pub_path),
                m=full_message,
                author=f"{author_name} <{author_email}>",
                allow_empty=True,
                env=sign_env,
            )
        finally:
            pub_path.unlink(missing_ok=True)
            allowed_signers.unlink(missing_ok=True)
    else:
        repo.git.commit(
            m=full_message,
            author=f"{author_name} <{author_email}>",
            allow_empty=True,
        )

    return repo.head.commit.hexsha


def _write_ssh_pubkey(private_key_path: Path, pub_path: Path) -> None:
    """Derive the SSH public key from a private key file using ssh-keygen.

    Raises RuntimeError if ssh-keygen fails (e.g., malformed key).
    """
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


def _write_allowed_signers(email: str, pub_path: Path) -> Path:
    """Write a temporary allowed_signers file for git SSH signature verification."""
    import os
    import tempfile

    pubkey_line = pub_path.read_text().strip()
    fd, path = tempfile.mkstemp(suffix="_allowed_signers")
    with os.fdopen(fd, "w") as f:
        f.write(f"{email} {pubkey_line}\n")
    return Path(path)


def get_commit_history(
    repo_path: Path,
    max_count: int = 50,
    since_hash: str | None = None,
) -> list[dict]:
    """Get commit history for an article.

    If *since_hash* is given, only commits reachable from HEAD but not
    from *since_hash* are included (``since_hash..HEAD``).

    Raises ValueError if the repo has no commits — the caller should
    commit before asking for history.
    """
    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")

    rev = f"{since_hash}..HEAD" if since_hash else None
    return [
        {
            "hash": c.hexsha,
            "parents": [p.hexsha for p in c.parents],
            "message": c.message.strip(),
            "author": str(c.author),
            "author_email": (c.author.email or "").strip() if c.author else "",
            "timestamp": c.committed_datetime.isoformat(),
            "stats": {
                "total": c.stats.total,
                "files": list(c.stats.files.keys()),
                "insertions": c.stats.total.get("insertions", 0) if isinstance(c.stats.total, dict) else 0,
                "deletions": c.stats.total.get("deletions", 0) if isinstance(c.stats.total, dict) else 0,
            },
        }
        for c in repo.iter_commits(rev=rev, max_count=max_count)
    ]


def _patch_text(d) -> str:
    """Decode a git diff patch to str."""
    if d is None:
        return ""
    if isinstance(d, bytes):
        return d.decode("utf-8", errors="replace")
    return str(d)


# Commit message prefixes for non-content commits — these commits are
# platform operations (review, status transition, merge) and their
# authors should NOT be counted as article authors.
_NON_CONTENT_PREFIXES = ("[review]", "[status]", "[merge]")


def get_commit_authors(
    repo_path: Path,
    since_hash: str | None = None,
) -> set[str]:
    """Return the set of user IDs from content-commit author emails.

    Only counts commits whose message does NOT start with a non-content
    prefix (``[review]``, ``[status]``, ``[merge]``) AND whose author
    email ends with ``@peerpedia``.  This excludes review commits,
    status-transition commits, merge commits, and commits authored by the
    system git config.
    """
    repo = git.Repo(repo_path)
    rev = f"{since_hash}..HEAD" if since_hash else None
    return {
        c.author.email.split("@", 1)[0]
        for c in repo.iter_commits(rev=rev)
        if c.author.email.endswith("@peerpedia")
        and not c.message.lstrip().startswith(_NON_CONTENT_PREFIXES)
    }


def get_diff_between(repo_path: Path, hash1: str, hash2: str) -> dict:
    """Get the diff between two arbitrary commits.

    hash1 is the "old" commit, hash2 is the "new" commit.
    """
    repo = git.Repo(repo_path)
    c1 = repo.commit(hash1)
    c2 = repo.commit(hash2)

    files_changed: list[str] = []
    diff_parts: list[str] = []
    total_insertions = 0
    total_deletions = 0
    diff_files: dict[str, dict[str, int]] = {}

    for d in c1.diff(c2, create_patch=True):
        fname = d.a_path or d.b_path or ""
        if d.a_path:
            files_changed.append(d.a_path)

        patch = _patch_text(d.diff)
        if not patch:
            continue

        diff_parts.append(patch)
        ins = sum(1 for l in patch.split("\n") if l.startswith("+") and not l.startswith("+++"))
        dels = sum(1 for l in patch.split("\n") if l.startswith("-") and not l.startswith("---"))
        diff_files[fname] = {"insertions": ins, "deletions": dels}
        total_insertions += ins
        total_deletions += dels

    return {
        "diff_text": "\n".join(diff_parts),
        "files": files_changed,
        "stats": {
            "total": {
                "insertions": total_insertions,
                "deletions": total_deletions,
                "lines": total_insertions + total_deletions,
            },
            "files": list(diff_files.keys()),
        },
    }


# ── Merge ─────────────────────────────────────────────────────────────────


class MergeConflictError(Exception):
    """Raised when a git merge encounters conflicts that can't auto-resolve."""

    pass


def merge_git_repos(target: Path, fork: Path, author_name: str) -> str:
    """Merge fork repo into target repo.

    ``fork`` is a filesystem path to the fork's git repository (e.g.
    ``~/.peerpedia/articles/def456``).  We add it as a git remote,
    fetch its refs, and merge.  The remote-tracking refs in
    ``.git/refs/remotes/fork-<name>/`` are a git implementation
    detail — they are NOT the source of truth for fork relationships.
    The DB (``Article.forked_from``) owns that.

    Raises MergeConflictError if the merge has conflicts.
    """
    import os

    target_repo = git.Repo(target)

    remote_name = f"fork-{fork.name}"
    try:
        target_repo.create_remote(remote_name, str(fork))
        target_repo.git.fetch(remote_name)

        # Fork repos have exactly one branch — take the first remote ref
        fork_ref = target_repo.remotes[remote_name].refs[0]

        # Set committer via env so the merge commit has a predictable author
        # rather than inheriting the system git config.
        merge_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": "system@peerpedia",
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": "system@peerpedia",
        }
        target_repo.git.merge(
            fork_ref.commit.hexsha,
            message=f"[merge] {fork.name}",
            env=merge_env,
        )

        merge_hash = target_repo.head.commit.hexsha
    except git.GitCommandError as e:
        # Abort merge if in progress
        try:
            target_repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Merge conflict: {e}") from e
    finally:
        try:
            target_repo.delete_remote(target_repo.remotes[remote_name])
        except (IndexError, AttributeError, git.GitCommandError):
            pass

    return merge_hash


# ── Review file reading ────────────────────────────────────────────────────


def list_review_dirs(repo_path: Path) -> list[str]:
    """Return directory names under reviews/ (reviewer IDs or anonymous hashes).

    Returns an empty list if reviews/ does not exist or is empty.
    """
    reviews_dir = repo_path / "reviews"
    if not reviews_dir.is_dir():
        return []
    return [d.name for d in reviews_dir.iterdir() if d.is_dir()]


def read_review_scores(repo_path: Path, reviewer_dir: str) -> dict | None:
    """Read reviews/{reviewer_dir}/scores.json and return the parsed dict.

    Returns None if the scores file does not exist.
    Raises json.JSONDecodeError if the file contains malformed JSON.
    """
    import json

    scores_file = repo_path / "reviews" / reviewer_dir / "scores.json"
    if not scores_file.is_file():
        return None
    return json.loads(scores_file.read_text())


def delete_article_repo(repo_path: Path) -> None:
    """Delete the git repository for an article (idempotent).

    Called by orchestration layer AFTER the database record has been deleted.
    """
    import shutil

    if repo_path.exists():
        shutil.rmtree(str(repo_path))


# ── Sync helpers ────────────────────────────────────────────────────────────


def get_head_hash(repo_path: Path) -> str:
    """Return the commit hash of HEAD.

    Raises ValueError if the repo has no commits.
    """
    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")
    return repo.head.commit.hexsha


def merge_fetch_head(repo_path: Path, *, ff_only: bool = True) -> str:
    """Merge FETCH_HEAD into the current branch. Returns the new HEAD hash.

    Raises MergeConflictError if the merge fails (e.g. non-fast-forward
    when *ff_only* is True).
    """
    repo = git.Repo(repo_path)
    merge_args = ["FETCH_HEAD", "--ff-only"] if ff_only else ["FETCH_HEAD"]
    try:
        repo.git.merge(*merge_args)
    except git.GitCommandError as e:
        try:
            repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Merge failed: {e}") from e
    return repo.head.commit.hexsha


def verify_commit_signature(
    repo_path: Path,
    commit_hash: str,
    pubkey_ssh_line: str,
    author_email: str,
) -> None:
    """Verify that *commit_hash* has a valid Ed25519 signature from *author_email*.

    *pubkey_ssh_line* must be a full SSH public key line
    (``"ssh-ed25519 AAAAC3NzaC1..."``) — it is written to a temporary
    allowed_signers file for git's verification.

    Raises RuntimeError if verification fails.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_verify_signers", delete=False
    ) as f:
        f.write(f"{author_email} {pubkey_ssh_line}\n")
    signers_path = Path(f.name)
    try:
        repo = git.Repo(repo_path)
        repo.git.config("gpg.format", "ssh")
        repo.git.config("gpg.ssh.allowedSignersFile", str(signers_path))
        repo.git.verify_commit(commit_hash)
    except git.GitCommandError as e:
        raise RuntimeError(
            f"Commit {commit_hash[:8]} by {author_email} "
            f"signature verification failed: {e.stderr.strip()}"
        ) from e
    finally:
        signers_path.unlink(missing_ok=True)


def clone_article_repo(src: Path, dst: Path) -> Path:
    """Clone *src* git repository to *dst*. Returns *dst*.

    *dst* must not already exist — git clone creates it.
    """
    git.Repo.clone_from(str(src), str(dst))
    return dst


def checkout_files(repo_path: Path, commit_hash: str) -> None:
    """Checkout all files from *commit_hash* into the working tree.

    Equivalent to ``git checkout <commit> -- .`` — restores the worktree
    to the state at *commit_hash* without moving HEAD.
    """
    repo = git.Repo(repo_path)
    repo.git.checkout(commit_hash, "--", ".")
