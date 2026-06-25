# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Create a new article as a draft."""

from __future__ import annotations

import uuid

from peerpedia_core.storage.db import Session
from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.config.params import make_peerpedia_email
from peerpedia_core.frontmatter import make_article_frontmatter
from peerpedia_core.storage.db.crud_article import create_article
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    init_article_repo,
)
from peerpedia_core.crypto import temp_signing_key


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
    if not title.strip():
        raise BadRequestError("Title is required")

    for aid in author_ids:
        if get_user(db, aid) is None:
            raise NotFoundError(f"Author '{aid}' not found")

    article_id = str(uuid.uuid4())
    rp = DEFAULT_ARTICLES_DIR / article_id
    init_article_repo(rp)
    ext = ".typ" if format == "typst" else ".md"
    fm = make_article_frontmatter(title, abstract, keywords, categories)
    (rp / f"article{ext}").write_text(fm + content)
    user = get_user(db, author_ids[0])
    if signing_key_bytes:
        with temp_signing_key(signing_key_bytes) as key_path:
            commit_hash = commit_article(
                rp, "Initial submission", user.name, make_peerpedia_email(user.id),
                signing_key=key_path, pubkey_hex=pubkey_hex,
            )
    else:
        commit_hash = commit_article(
            rp, "Initial submission", user.name, make_peerpedia_email(user.id),
            signing_key=None, pubkey_hex=pubkey_hex,
        )

    a = create_article(
        db, id=article_id, title=title, abstract=abstract,
        keywords=keywords, categories=categories,
        authors=author_ids, status="draft",
    )
    a.last_author_rebuild_hash = commit_hash

    for aid in author_ids:
        add_maintainer(db, article_id, aid)

    return {"id": article_id, "title": title, "status": "draft", "commit_hash": commit_hash}
