# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Create a new article as a draft."""

from __future__ import annotations

import uuid
from contextlib import nullcontext

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import (
    article_filename, article_format_to_ext, make_peerpedia_email,
)
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.frontmatter import make_article_frontmatter
from peerpedia_core.storage.db.crud_article import create_article
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.git_backend import commit_article, init_article_repo
from peerpedia_core.crypto import temp_signing_key
from peerpedia_core.commands.guards import require_authors_exist, require_title_nonempty, require_user


def _write_initial_article(rp, *, title, content, abstract, keywords, categories, format) -> str:
    """Write the initial article file. Returns the file extension used."""
    ext = article_format_to_ext(format)
    fm = make_article_frontmatter(title, abstract, keywords, categories)
    (rp / article_filename(ext)).write_text(fm + content)
    return ext


def create_article_with_content(
    db: Session, *, title: str, content: str, author_ids: list[str],
    format: str = "markdown", abstract: str | None = None,
    keywords: str | None = None, categories: str | None = None,
    signing_key_bytes: bytes | None = None, pubkey_hex: str | None = None,
) -> dict:
    """Create an article as a draft.

    If *signing_key_bytes* and *pubkey_hex* are provided, the initial commit
    is signed via SSH and the pubkey is embedded in the commit message.

    Returns:
        {"id": <article_id>, "title": ..., "status": "draft", "commit_hash": ...}

    Raises BadRequestError if the title is empty.
    Raises NotFoundError if any author is not found.
    """
    # ── Validate ────────────────────────────────────────────────────────────
    require_title_nonempty(title)
    require_authors_exist(db, author_ids)

    # ── Create git repo ─────────────────────────────────────────────────────
    article_id = str(uuid.uuid4())
    rp = article_repo_path(article_id)
    init_article_repo(rp)

    # ── Write initial file ──────────────────────────────────────────────────
    _write_initial_article(
        rp, title=title, content=content, abstract=abstract,
        keywords=keywords, categories=categories, format=format,
    )

    # ── Commit ──────────────────────────────────────────────────────────────
    user = require_user(db, author_ids[0])
    with (temp_signing_key(signing_key_bytes) if signing_key_bytes else nullcontext()) as key_path:
        commit_hash = commit_article(
            rp, "Initial submission", user.name, make_peerpedia_email(user.id),
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )

    # ── Create DB record ────────────────────────────────────────────────────
    a = create_article(
        db, id=article_id, title=title, abstract=abstract,
        keywords=keywords, categories=categories,
        authors=author_ids, status="draft",
    )
    a.last_author_rebuild_hash = commit_hash

    # ── Seed maintainers ────────────────────────────────────────────────────
    for aid in author_ids:
        add_maintainer(db, article_id, aid)

    return {"id": article_id, "title": title, "status": "draft", "commit_hash": commit_hash}
