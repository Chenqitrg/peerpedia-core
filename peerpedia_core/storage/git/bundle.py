# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git bundle protocol — create and ingest incremental git bundles."""

import tempfile
from pathlib import Path

import git

from peerpedia_core.storage.git.read import is_ancestor
from peerpedia_core.types import short_id


def get_head(repo_path: Path) -> str:
    """Return the HEAD commit hash.

    Raises FileNotFoundError if no .git directory, ValueError if no commits.
    """
    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError("REPO_NOT_FOUND")
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
    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError("REPO_NOT_FOUND")

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
    """
    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError("REPO_NOT_FOUND")

    if since_hash is not None and not is_ancestor(repo_path, since_hash):
        raise ValueError(f"INVALID_SINCE_HASH: {short_id(since_hash)}")

    repo = git.Repo(repo_path)
    rev_range = f"{since_hash}..HEAD" if since_hash else "HEAD"
    proc = repo.git.bundle("create", "-", rev_range, as_process=True)
    stdout, _stderr = proc.communicate()
    return stdout
