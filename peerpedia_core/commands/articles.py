# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Article lifecycle — the six core operations on articles.

Call graph (► = calls, ▻ = deferred import)::

    create_article_with_content
      ├► git_backend.init_article_repo
      ├► git_backend.commit_article
      └► crud_article.create_article           (flush only)

    update_article_content
      ├► policies.assert_can_edit_article      (draft or published only)
      ├► git_backend.commit_article
      ├► crud_article helpers                  (title, abstract, etc.)
      ├► rebuild_article_authors
      └► crud_article.set_sink_start           (if old_status == "published")

    publish_article
      ├► policies.assert_can_publish_article
      ├► assert old_status == "draft"          (G10 — draft only)
      ├▻ commands.reviews.write_review_to_git (deferred import)
      ├► crud_review.upsert_review
      ├► crud_article.set_sink_start           (7 days for new, 3 for re-entry)
      ├► commands.workflow.recompute_article_score
      └► policies.require_self_review_for_publish  (G6 — gate after write)

    fork_article
      ├► policies.assert_can_fork_article      (published only, no dupes)
      ├► git (Repo.clone_from)
      ├► git_backend.get_commit_authors
      └► crud_article.create_article

    rollback_article
      ├► policies.assert_can_rollback_article
      ├► git (checkout + commit)
      ├► crud_article.set_sink_start           (only if old_status == "published")
      ├► rebuild_article_authors
      └► commands.workflow.recompute_article_score

    rebuild_article_authors
      ├► git_backend.get_commit_authors        (extract user IDs from commit emails)
      └► crud_article.add_article_authors      (merge new authors into DB)

State transitions enforced here
-------------------------------
- publish_article: draft → sedimentation (G10: draft only)
- update_article_content: published → sedimentation (G2: auto 3-day sink)
- rollback_article: published → sedimentation (G3: auto sink); draft → draft
- fork_article: published → new draft (fork)
- All functions call ``session.flush()`` only; commit is the caller's duty.

Reviewer's checklist
--------------------
- Is every git write followed by a corresponding DB cache update?
- Are policy checks (assert_can_*) called before any mutation?
- Does the state machine transition match the docstring and architecture.md?
- For published→sedimentation triggers: is ``old_status`` captured *before*
  any status mutation?

TODO(security): local integrity check — on article access (show, edit,
publish), verify git commits are signed and DB matches git SOT.  If
unsigned commits or DB tampering are detected, refuse operations and
force a repair from git history.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.config.params import params
from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.frontmatter import make_article_frontmatter, strip_frontmatter
from peerpedia_core.policies.articles import (
    assert_can_delete_article,
    assert_can_edit_article,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_rollback_article,
    require_self_review_for_publish,
)
from peerpedia_core.storage.db.crud_article import (
    add_article_authors,
    count_articles as _count,
    create_article,
    delete_article as _delete,
    get_article as _get_article,
    get_article_by_fork_and_author,
    get_author_ids as _get_author_ids,
    increment_fork_count,
    list_articles as _list,
    set_sink_start,
    update_article_status,
)
from peerpedia_core.storage.db.crud_maintainer import add_maintainer, get_maintainer_ids
from peerpedia_core.storage.db.crud_review import get_review, upsert_review
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked as _is_bookmarked
from peerpedia_core.storage.db.crud_user import get_following as _get_following, get_user
from peerpedia_core.crypto import write_temp_key
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    checkout_files,
    clone_article_repo,
    commit_article,
    delete_article_repo,
    get_commit_authors,
    get_head_hash,
    init_article_repo,
)
from peerpedia_core.storage.locks import get_article_lock
from peerpedia_core.commands.reviews import write_review_to_git
from peerpedia_core.commands.workflow import recompute_article_score, recompute_author_reputation


# ── Helpers ──────────────────────────────────────────────────────────────────


def rebuild_article_authors(db: Session, article_id: str, since_hash: str | None = None) -> None:
    """Read author IDs from git commits and merge them into DB.

    Sets ``last_author_rebuild_hash`` to the current HEAD so the next
    rebuild only scans new commits (*since_hash*).
    """
    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError(f"Article not found: {article_id}")

    rp = DEFAULT_ARTICLES_DIR / article_id
    head_hash = get_head_hash(rp)
    new_ids = get_commit_authors(rp, since_hash=since_hash)

    existing = set(_get_author_ids(db, article_id))
    new_only = [a for a in new_ids if a not in existing]
    if new_only:
        add_article_authors(db, article_id, new_only)

    article.last_author_rebuild_hash = head_hash


# ═══════════════════════════════════════════════════════════════════════════════
# Fork
# ═══════════════════════════════════════════════════════════════════════════════


def fork_article(db: Session, article_id: str, user_id: str) -> dict:
    """Fork an article: clone its git repo and create a new Article record.

    Returns:
        {"id": <fork_id>, "forked_from": <original_id>, "status": "draft"}

    Raises:
        NotFoundError: user not found in DB
        NotAuthorizedError: article not forkable (policy)
        ConflictError: user already forked this article
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    original = get_article(db, article_id)
    if original is None:
        raise NotFoundError("Article not found")
    existing_fork = get_article_by_fork_and_author(db, forked_from=article_id, author_id=user.id)
    assert_can_fork_article(original, existing_fork)

    fork_id = str(uuid.uuid4())
    src = DEFAULT_ARTICLES_DIR / article_id
    dst = DEFAULT_ARTICLES_DIR / fork_id

    clone_article_repo(src, dst)

    # Derive authors from git first, then write DB — git is the SOT.
    # Original authors from git history remain as ArticleAuthor
    # (they contributed content), but only the forker is ScriptMaintainer
    # (they manage the fork).
    git_authors = get_commit_authors(dst) | {user_id}

    fork = create_article(
        db,
        id=fork_id,
        title=original.title,
        abstract=original.abstract,
        keywords=original.keywords,
        categories=original.categories,
        authors=sorted(git_authors),
        status="draft",
        forked_from=article_id,
    )
    # Seed maintainer: only the forker manages the fork.
    add_maintainer(db, fork_id, user_id)
    increment_fork_count(db, article_id)

    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


# ═══════════════════════════════════════════════════════════════════════════════
# Rollback
# ═══════════════════════════════════════════════════════════════════════════════


def rollback_article(
    db: Session,
    article_id: str,
    target_hash: str,
    user_id: str,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Rollback to a previous commit (creates a new revert commit, not force-push).

    Returns:
        {"commit_hash": <new_hash>, "message": "Rollback to ..."}

    Raises:
        NotAuthorizedError: user lacks rollback permission
        NotFoundError: article repo not found
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_rollback_article(article, mids, user)
    old_status = article.status
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found")

    checkout_files(rp, target_hash)

    author_name = user.name
    key_path = write_temp_key(signing_key_bytes) if signing_key_bytes else None
    try:
        new_hash = commit_article(
            rp, f"Rollback to {target_hash[:8]}", author_name, f"{user_id}@peerpedia",
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )
    finally:
        if key_path:
            key_path.unlink(missing_ok=True)

    # G3: only trigger sedimentation for published articles
    if old_status == "published":
        set_sink_start(db, article_id, params.sink.edit_article_default_days)

    # Sync DB state after the new commit: authors, score, rebuild hash.
    rebuild_article_authors(db, article_id)
    recompute_article_score(db, article_id)

    msg = f"Rollback to {target_hash[:8]}"
    return {"id": article.id, "title": article.title, "status": article.status,
            "commit_hash": new_hash, "message": msg}


# ═══════════════════════════════════════════════════════════════════════════════
# Create
# ═══════════════════════════════════════════════════════════════════════════════


def create_article_with_content(
    db: Session,
    *,
    title: str,
    content: str,
    author_ids: list[str],
    format: str = "markdown",
    abstract: str | None = None,
    keywords: str | None = None,
    categories: str | None = None,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Create an article as a draft.

    Articles are always created as ``draft``.  To publish with self-review
    and start the sink timer, call ``publish_article``.

    If *signing_key_bytes* and *pubkey_hex* are provided, the initial commit
    is signed via SSH and the pubkey is embedded in the commit message.

    Returns:
        {"id": <article_id>, "title": ..., "status": "draft", "commit_hash": ...}

    Raises:
        NotFoundError: author not found in DB
    """
    if not title.strip():
        raise BadRequestError("Title is required")

    for aid in author_ids:
        if get_user(db, aid) is None:
            raise NotFoundError(f"Author '{aid}' not found")

    article_id = str(uuid.uuid4())

    # Git first — init repo, write article.md with frontmatter, commit.

    rp = DEFAULT_ARTICLES_DIR / article_id
    init_article_repo(rp)
    (rp / ".gitignore").write_text("""\
# PeerPedia article repo — only approved paths are tracked.
# Prevents free-riding by blocking arbitrary files from being committed.
*
!.gitignore
!article.md
!article.typ
!reviews/
!reviews/**
!compiled/
!compiled/**
""")
    ext = ".typ" if format == "typst" else ".md"
    fm = make_article_frontmatter(title, abstract, keywords, categories)
    (rp / f"article{ext}").write_text(fm + content)
    user = get_user(db, author_ids[0])
    key_path = write_temp_key(signing_key_bytes) if signing_key_bytes else None
    try:
        commit_hash = commit_article(
            rp, "Initial submission", user.name, f"{user.id}@peerpedia",
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )
    finally:
        if key_path:
            key_path.unlink(missing_ok=True)

    # Then DB — git is the SOT.
    a = create_article(
        db,
        id=article_id,
        title=title,
        abstract=abstract,
        keywords=keywords,
        categories=categories,
        authors=author_ids,
        status="draft",
    )
    a.last_author_rebuild_hash = commit_hash

    # Seed maintainers: all initial authors are also maintainers.
    for aid in author_ids:
        add_maintainer(db, article_id, aid)

    return {
        "id": article_id, "title": title, "status": "draft",
        "commit_hash": commit_hash,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Update
# ═══════════════════════════════════════════════════════════════════════════════


def update_article_content(
    db: Session,
    article_id: str,
    *,
    content: str | None = None,
    title: str | None = None,
    abstract: str | None = None,
    keywords: str | None = None,
    categories: str | None = None,
    message: str,
    user_id: str,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Edit an article: update content/metadata, commit to git.

    Returns:
        {"id": <article_id>, "title": ..., "status": ..., "commit_hash": ...}
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    a = get_article(db, article_id)
    if a is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_edit_article(a, mids, user)
    old_status = a.status
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found")

    # Determine the file extension
    ext = ".md"
    for e in [".md", ".typ"]:
        if (rp / f"article{e}").exists():
            ext = e
            break
    article_path = rp / f"article{ext}"

    # Build new frontmatter from current values

    new_title = title if title is not None else a.title
    new_abstract = abstract if abstract is not None else a.abstract
    new_keywords = keywords if keywords is not None else a.keywords
    new_categories = categories if categories is not None else a.categories
    new_fm = make_article_frontmatter(new_title, new_abstract, new_keywords, new_categories)

    # Get body: use provided content, or extract from existing file
    if content is not None:
        body = content
    else:
        body = strip_frontmatter(article_path.read_text())

    article_path.write_text(new_fm + body)

    # Git commit first — then sync DB.
    key_path = write_temp_key(signing_key_bytes) if signing_key_bytes else None
    try:
        commit_hash = commit_article(
            rp, message, user.name, f"{user_id}@peerpedia",
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )
    finally:
        if key_path:
            key_path.unlink(missing_ok=True)

    # DB metadata follows git.
    if title is not None:
        a.title = title
    if abstract is not None:
        a.abstract = abstract
    if keywords is not None:
        a.keywords = keywords
    if categories is not None:
        a.categories = categories

    rebuild_article_authors(db, article_id, since_hash=a.last_author_rebuild_hash)

    # G2: any commit after published triggers 3-day sedimentation
    if old_status == "published":
        set_sink_start(db, article_id, params.sink.edit_article_default_days)

    return {
        "id": a.id, "title": a.title, "status": a.status,
        "commit_hash": commit_hash,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Publish
# ═══════════════════════════════════════════════════════════════════════════════


def publish_article(
    db: Session,
    article_id: str,
    user_id: str,
    self_review: dict,
    *,
    comment: str = "",
) -> dict:
    """Publish an article to the sedimentation pool.

    Only callable from ``draft`` status.  Writes the self-review to git,
    caches scores in DB, starts the sink timer, and recomputes the article
    score.

    Raises:
        NotFoundError: article or user not found
        NotAuthorizedError: user cannot publish this article
        BadRequestError: self-review missing or article already published
    """

    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    a = get_article(db, article_id)
    if a is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_publish_article(a, mids, user)

    # G10: publish only from draft
    old_status = a.status
    if old_status != "draft":
        raise NotAuthorizedError("Only draft articles can be published")

    # Write self-review to git — the publisher's own review (real name).

    write_review_to_git(
        article_id, user_id, self_review, comment, user.name, f"{user_id}@peerpedia",
    )

    # Record status transition in git so it survives P2P sync.
    commit_hash = commit_article(
        DEFAULT_ARTICLES_DIR / article_id,
        "[status] sedimentation",
        "PeerPedia",
        "system@peerpedia",
    )

    # Enter sedimentation so scope derivation works.
    update_article_status(db, article_id, "sedimentation")


    # Cache scores in DB.
    upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=user_id, scores=self_review,
    )

    # G1: use old_status (before status change) to decide sink duration
    sink_days = (
        params.sink.new_article_default_days
        if old_status == "draft"
        else params.sink.edit_article_default_days
    )
    set_sink_start(db, article_id, sink_days)

    # Recompute score.
    recompute_article_score(db, article_id)

    # G6: self-review must exist and score must be computed
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise BadRequestError("self_review is required before publishing — no git repo found")
    try:
        head = get_head_hash(rp)
    except ValueError:
        raise BadRequestError("self_review is required before publishing — no commits yet")
    existing_review = get_review(db, article_id, user.id, a.status, head)
    require_self_review_for_publish(a, existing_review)

    return {"id": a.id, "title": a.title, "status": a.status, "commit_hash": commit_hash}


# ═══════════════════════════════════════════════════════════════════════════════
# Read wrappers — thin pass-through to crud, so CLI doesn't import storage/db
# ═══════════════════════════════════════════════════════════════════════════════


def get_article(db: Session, article_id: str):
    """Return an article by ID, or None."""
    return _get_article(db, article_id)


def list_articles(
    db: Session,
    status: str | set[str] | None = None,
    search_query: str | None = None,
    author_id: str | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list:
    """List articles with AND filters. Pipeline: SQL first, then Python narrowing."""
    articles = _list(db, status=status, search_query=search_query)
    if author_id:
        articles = [a for a in articles if author_id in _get_author_ids(db, a.id)]
    if viewer_id:
        followed = {u.id for u in _get_following(db, viewer_id)}
        articles = [a for a in articles if any(aid in followed for aid in _get_author_ids(db, a.id))]
    if bookmarked_by:
        articles = [a for a in articles if _is_bookmarked(db, bookmarked_by, a.id)]
    if offset:
        articles = articles[offset:]
    if limit is not None:
        articles = articles[:limit]
    return articles


def count_articles(db: Session, **kwargs) -> int:
    """Count articles with optional filters."""
    return _count(db, **kwargs)


def get_author_ids(db: Session, article_id: str) -> list[str]:
    """Return ordered author IDs for an article."""
    return _get_author_ids(db, article_id)


def delete_article(db: Session, article_id: str, *, user_id: str) -> None:
    """Delete an article from DB and its git repo.

    Only callable from ``draft`` status by an author.  Sedimentation and
    published articles cannot be deleted.
    """

    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_delete_article(article, mids, user)

    _delete(db, article_id)
    delete_article_repo(DEFAULT_ARTICLES_DIR / article_id)
