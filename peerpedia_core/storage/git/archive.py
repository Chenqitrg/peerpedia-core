# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Full-repo pack/unpack — tar.gz archive transfer.

Caller must validate that *repo_path* does not already exist
before calling ``ingest_article_repo``.
"""

from pathlib import Path

from peerpedia_core.storage.git.bundle import get_head


def ingest_article_repo(repo_path: Path, payload: dict[str, str]) -> str:
    """Unpack a full article repo from a base64-encoded tar.gz payload.

    *payload* must contain ``"repo_bundle"``: a base64-encoded gzipped
    tar archive of the full git repo.  Returns the HEAD hash.
    """
    import base64 as _b64
    import io as _io
    import tarfile as _tarfile

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
