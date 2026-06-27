# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Update an article's content and metadata."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import (
    article_filename, article_format_to_ext, make_peerpedia_email, params,
)
from peerpedia_core.frontmatter import make_article_frontmatter, strip_frontmatter
from peerpedia_core.core.guards import guard_closes_trailer
from peerpedia_core.rules.articles import assert_can_edit_article
from peerpedia_core.core.reconcile import reconcile_integrity
from peerpedia_core.storage.db.crud_article import (
    clear_publish_consents,
)
from peerpedia_core.storage.git import commit_article, resolve_article_format
from peerpedia_core.crypto import temp_signing_key
from peerpedia_core.core.articles._helpers import reset_sink
from peerpedia_core.core.reconcile import reconcile_authors
from peerpedia_core.storage.db.guards import authorize_article_action
from peerpedia_core.storage.git.guards import require_article_repo

def _rewrite_article_file(
    rp: Path, a, *, title, abstract, keywords, categories, content,
) -> None:
    """Write updated frontmatter + body to the article source file."""
    fmt = resolve_article_format(rp)
    article_path = rp / article_filename(article_format_to_ext(fmt))

    new_title = title if title is not None else a.title
    new_abstract = abstract if abstract is not None else a.abstract
    new_keywords = keywords if keywords is not None else a.keywords
    new_categories = categories if categories is not None else a.categories
    new_fm = make_article_frontmatter(new_title, new_abstract, new_keywords, new_categories)

    body = content if content is not None else strip_frontmatter(article_path.read_text())
    article_path.write_text(new_fm + body)


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

    Raises NotFoundError if the user, article, or article repo is not found.
    Raises BadRequestError if a required Closes: trailer is missing or invalid.
    """
    # ── Authorization ──────────────────────────────────────────────────────
    reconcile_integrity(db, article_id, level="light")
    user, a, mids = authorize_article_action(db, article_id, user_id)
    assert_can_edit_article(a, mids, user)
    old_status = a.status

    # ── Validation ─────────────────────────────────────────────────────────
    if old_status == "sedimentation":
        guard_closes_trailer(message, article_id)

    # ── Write file ─────────────────────────────────────────────────────────
    rp = require_article_repo(article_id)
    _rewrite_article_file(
        rp, a, title=title, abstract=abstract, keywords=keywords,
        categories=categories, content=content,
    )

    # ── Commit ─────────────────────────────────────────────────────────────
    author_email = make_peerpedia_email(user_id)
    if signing_key_bytes:
        with temp_signing_key(signing_key_bytes) as key_path:
            commit_hash = commit_article(
                rp, message, user.name, author_email,
                signing_key=key_path, pubkey_hex=pubkey_hex,
            )
    else:
        commit_hash = commit_article(
            rp, message, user.name, author_email,
            signing_key=None, pubkey_hex=pubkey_hex,
        )

    # ── Update DB metadata ─────────────────────────────────────────────────
    for field in ("title", "abstract", "keywords", "categories"):
        val = locals()[field]
        if val is not None:
            setattr(a, field, val)
    clear_publish_consents(db, article_id)
    reconcile_authors(db, article_id, since_hash=a.last_author_rebuild_hash)

    # ── Sink timer ─────────────────────────────────────────────────────────
    if old_status in ("sedimentation", "published"):
        extra = params.sink.edit_article_default_days
        reset_sink(db, article_id, rp, extra)
        if a.total_sink_days_accumulated + extra <= params.sink.max_total_sink_days:
            a.total_sink_days_accumulated += extra
            a.sink_extended_count += 1

    return {"id": a.id, "title": a.title, "status": a.status, "commit_hash": commit_hash}
