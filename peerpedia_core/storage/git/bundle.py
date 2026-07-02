# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git bundle protocol — create and ingest incremental git bundles.

Callers must validate repo existence via ``require_article_repo``
and, for ``create_bundle``, that *since_hash* is a valid ancestor.
"""

import tempfile
from pathlib import Path

import git


def get_head(repo_path: Path) -> str:
    """Return the HEAD commit hash.  Caller must validate repo is initialised."""
    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError("REPO_NO_COMMITS")
    return repo.head.commit.hexsha


def ingest_bundle(repo_path: Path, bundle_bytes: bytes) -> None:
    """Verify and fetch git bundle objects into the local repo.

    Pure git — adds objects to ``.git/objects`` but does NOT merge or
    touch the working tree.  The caller is responsible for merging
    ``FETCH_HEAD`` and reconciling DB state.
    """
    repo = git.Repo(repo_path)
    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
        f.write(bundle_bytes)
        f.flush()
        try:
            try:
                repo.git.bundle("verify", f.name)
            except git.GitCommandError as e:
                raise ValueError(f"Invalid bundle: {e}") from e

            try:
                repo.git.fetch(f.name, "HEAD")
            except git.GitCommandError as e:
                raise ValueError(f"Bundle fetch failed: {e}") from e
        finally:
            Path(f.name).unlink(missing_ok=True)


def create_bundle(repo_path: Path, since_hash: str | None = None) -> bytes:
    """Create a git bundle from *since_hash* to HEAD.

    *since_hash=None* → full bundle.  Otherwise incremental (``since_hash..HEAD``).
    Caller must validate *since_hash* is an ancestor of HEAD.
    """
    repo = git.Repo(repo_path)
    rev_range = f"{since_hash}..HEAD" if since_hash else "HEAD"
    proc = repo.git.bundle("create", "-", rev_range, as_process=True)
    stdout, _stderr = proc.communicate()
    return stdout
