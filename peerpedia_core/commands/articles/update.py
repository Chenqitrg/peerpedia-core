# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Update an article's content and metadata."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.frontmatter import make_article_frontmatter, strip_frontmatter
from peerpedia_core.policies.articles import assert_can_edit_article
from peerpedia_core.storage.db.crud_article import (
    get_article as _get_article,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, commit_article
from peerpedia_core.crypto import write_key_to_tempfile
from peerpedia_core.commands.articles._helpers import rebuild_article_authors


def update_article_content(
    db: Session, article_id: str, *, content: str | None = None,
    title: str | None = None, abstract: str | None = None,
    keywords: str | None = None, categories: str | None = None,
    message: str, user_id: str, signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Edit an article: update content/metadata, commit to git.

    Returns:
        {"id": <article_id>, "title": ..., "status": ..., "commit_hash": ...}
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    a = _get_article(db, article_id)
    if a is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_edit_article(a, mids, user)
    old_status = a.status
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found")

    ext = ".md"
    for e in [".md", ".typ"]:
        if (rp / f"article{e}").exists():
            ext = e
            break
    article_path = rp / f"article{ext}"

    new_title = title if title is not None else a.title
    new_abstract = abstract if abstract is not None else a.abstract
    new_keywords = keywords if keywords is not None else a.keywords
    new_categories = categories if categories is not None else a.categories
    new_fm = make_article_frontmatter(new_title, new_abstract, new_keywords, new_categories)

    body = content if content is not None else strip_frontmatter(article_path.read_text())
    article_path.write_text(new_fm + body)

    key_path = write_key_to_tempfile(signing_key_bytes) if signing_key_bytes else None
    try:
        commit_hash = commit_article(
            rp, message, user.name, f"{user_id}@peerpedia",
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )
    finally:
        if key_path:
            key_path.unlink(missing_ok=True)

    if title is not None:
        a.title = title
    if abstract is not None:
        a.abstract = abstract
    if keywords is not None:
        a.keywords = keywords
    if categories is not None:
        a.categories = categories

    rebuild_article_authors(db, article_id, since_hash=a.last_author_rebuild_hash)

    if old_status == "published":
        set_sink_start(db, article_id, params.sink.edit_article_default_days)

    return {"id": a.id, "title": a.title, "status": a.status, "commit_hash": commit_hash}
