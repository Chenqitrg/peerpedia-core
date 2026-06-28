# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Full-repo pack/unpack — tar.gz archive transfer."""

from pathlib import Path

from peerpedia_core.exceptions import ConflictError
from peerpedia_core.storage.git.bundle import get_head


def ingest_article(repo_path: Path, payload: dict[str, str]) -> str:
    """Receive and unpack a full article repo upload.

    Thin wrapper around ``ingest_article_repo`` that converts
    ``FileExistsError`` to ``ConflictError`` for the caller.
    """
    try:
        return ingest_article_repo(repo_path, payload)
    except FileExistsError:
        raise ConflictError(code="ARTICLE_ALREADY_EXISTS") from None


def ingest_article_repo(repo_path: Path, payload: dict[str, str]) -> str:
    """Unpack a full article repo from a base64-encoded tar.gz payload.

    *payload* must contain ``"repo_bundle"``: a base64-encoded gzipped
    tar archive of the full git repo.  Returns the HEAD hash.
    """
    import base64 as _b64
    import io as _io
    import tarfile as _tarfile

    if (repo_path / ".git").is_dir():
        raise FileExistsError(f"Article already exists locally: {repo_path.name}")

    bundle_bytes = _b64.b64decode(payload["repo_bundle"])
    with _tarfile.open(fileobj=_io.BytesIO(bundle_bytes), mode="r:gz") as tar:
        tar.extractall(path=repo_path.parent)
    return get_head(repo_path)


def pack_article_repo(repo_path: Path) -> str:
    """Pack an article's full git repo into a base64-encoded tar.gz string."""
    import base64 as _b64
    import io as _io
    import tarfile as _tarfile

    buf = _io.BytesIO()
    with _tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(repo_path), arcname=repo_path.name)
    return _b64.b64encode(buf.getvalue()).decode("ascii")
