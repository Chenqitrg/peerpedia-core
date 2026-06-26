# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Update an article's content and metadata."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import (
    article_filename, article_format_to_ext, make_peerpedia_email, params,
)
from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.frontmatter import make_article_frontmatter, strip_frontmatter
from peerpedia_core.policies.articles import assert_can_edit_article, assert_not_folded
from peerpedia_core.commands.integrity import assert_article_integrity
from peerpedia_core.commands.trailers import parse_closes_trailer, validate_closes_target
from peerpedia_core.storage.db.crud_article import (
    clear_publish_consents,
)
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.git_backend import commit_article, resolve_article_format
from peerpedia_core.crypto import temp_signing_key
from peerpedia_core.commands.articles._helpers import (
    reset_sink,
    rebuild_article_authors,
    require_article,
    require_article_repo,
    require_user,
)

def _require_closes_trailer(message: str, article_id: str) -> None:
    """Raise BadRequestError if *message* lacks a valid Closes: trailer.

    Only called during sedimentation — edits must reference a review thread.
    """
    if not message:
        raise BadRequestError(
            "Sedimentation edits require a Closes: review/{dir}/thread-{n} "
            "trailer in the commit message"
        )
    parsed = parse_closes_trailer(message)
    if parsed is None:
        raise BadRequestError(
            "Sedimentation edits must reference a review thread via "
            "Closes: review/{reviewer-dir}/thread-{n} in the commit message"
        )
    reviewer_dir, thread_num = parsed
    if not validate_closes_target(article_id, reviewer_dir, thread_num):
        raise BadRequestError(
            f"Closes target not found: review/{reviewer_dir}/thread-{thread_num:03d}"
        )


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
    assert_article_integrity(db, article_id, level="light")
    user = require_user(db, user_id)
    a = require_article(db, article_id)
    mids = get_maintainer_ids(db, article_id)
    assert_not_folded(a, threshold=params.reputation.fold_score_threshold)
    assert_can_edit_article(a, mids, user)
    old_status = a.status

    # ── Validation ─────────────────────────────────────────────────────────
    if old_status == "sedimentation":
        _require_closes_trailer(message, article_id)

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
    rebuild_article_authors(db, article_id, since_hash=a.last_author_rebuild_hash)

    # ── Sink timer ─────────────────────────────────────────────────────────
    if old_status in ("sedimentation", "published"):
        extra = params.sink.edit_article_default_days
        reset_sink(db, article_id, rp, extra)
        if a.total_sink_days_accumulated + extra <= params.sink.max_total_sink_days:
            a.total_sink_days_accumulated += extra
            a.sink_extended_count += 1

    return {"id": a.id, "title": a.title, "status": a.status, "commit_hash": commit_hash}
