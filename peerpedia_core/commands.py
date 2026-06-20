# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article orchestration commands.

Each function combines core primitives (CRUD, git, policies, workflow) into
a single business operation.  Callers (CLI, backend routes) own the transaction
boundary — these functions do NOT call ``db.commit()``.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import git as gitmod
from sqlalchemy.orm import Session

from peerpedia_core.config.params import params

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.policies.articles import (
    assert_can_edit_article,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_rollback_article,
    assert_can_submit_review,
)
from peerpedia_core.storage.db.crud_article import (
    add_article_authors,
    create_article,
    get_article,
    get_author_ids,
    increment_fork_count,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_merge import (
    accept_merge_proposal,
    get_merge_proposal,
)
from peerpedia_core.storage.db.crud_review import (
    upsert_review,
)
from peerpedia_core.storage.db.crud_user import derive_anonymous_name, get_user
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    MergeConflictError,
    commit_article,
    get_commit_authors,
    init_article_repo,
    merge_git_repos,
)
from peerpedia_core.storage.locks import get_article_lock
from peerpedia_core.workflow.reputation import compute_author_reputation
from peerpedia_core.workflow.scoring import compute_article_score


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
    head_hash = gitmod.Repo(rp).head.commit.hexsha
    new_ids = get_commit_authors(rp, since_hash=since_hash)

    existing = set(get_author_ids(db, article_id))
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

    original = assert_can_fork_article(db, article_id, user)

    fork_id = str(uuid.uuid4())
    src = DEFAULT_ARTICLES_DIR / article_id
    dst = DEFAULT_ARTICLES_DIR / fork_id

    gitmod.Repo.clone_from(str(src), str(dst))

    # Derive authors from git first, then write DB — git is the SOT.
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
    increment_fork_count(db, article_id)

    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


# ═══════════════════════════════════════════════════════════════════════════════
# Rollback
# ═══════════════════════════════════════════════════════════════════════════════


def rollback_article(db: Session, article_id: str, target_hash: str, user_id: str) -> dict:
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

    article = assert_can_rollback_article(db, article_id, user)
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found")

    repo = gitmod.Repo(rp)
    repo.git.checkout(target_hash, "--", ".")

    author_name = user.name
    new_hash = commit_article(
        rp, f"Rollback to {target_hash[:8]}", author_name, f"{user_id}@peerpedia",
    )
    set_sink_start(db, article_id, params.sink.edit_article_default_days)

    # Sync DB state after the new commit: authors, score, rebuild hash.
    rebuild_article_authors(db, article_id)
    score = compute_article_score(db, article_id)
    if score is not None:
        a = get_article(db, article_id)
        a.score = score

    return {"commit_hash": new_hash, "message": f"Rollback to {target_hash[:8]}"}


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
) -> dict:
    """Create an article as a draft.

    Articles are always created as ``draft``.  To publish with self-review
    and start the sink timer, call ``publish_article``.

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
    from peerpedia_core.storage.compiler import make_article_frontmatter

    rp = DEFAULT_ARTICLES_DIR / article_id
    init_article_repo(rp)
    ext = ".typ" if format == "typst" else ".md"
    fm = make_article_frontmatter(title, abstract, keywords, categories)
    (rp / f"article{ext}").write_text(fm + content)
    user = get_user(db, author_ids[0])
    commit_hash = commit_article(
        rp, "Initial submission", user.name, f"{user.id}@peerpedia",
    )

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
    message: str = "Edit: content updated",
    user_id: str,
) -> dict:
    """Edit an article: update content/metadata, commit to git.

    Returns:
        {"id": <article_id>, "title": ..., "status": ..., "commit_hash": ...}
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    a = assert_can_edit_article(db, article_id, user)
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
    from peerpedia_core.storage.compiler import make_article_frontmatter, _strip_frontmatter

    new_title = title if title is not None else a.title
    new_abstract = abstract if abstract is not None else a.abstract
    new_keywords = keywords if keywords is not None else a.keywords
    new_categories = categories if categories is not None else a.categories
    new_fm = make_article_frontmatter(new_title, new_abstract, new_keywords, new_categories)

    # Get body: use provided content, or extract from existing file
    if content is not None:
        body = content
    else:
        body = _strip_frontmatter(article_path.read_text())

    article_path.write_text(new_fm + body)

    # Git commit first — then sync DB.
    commit_hash = commit_article(rp, message, user.name, f"{user_id}@peerpedia")

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

    Writes the self-review to git, caches scores in DB, starts the sink
    timer, and recomputes the article score.

    Raises:
        NotFoundError: article or user not found
        NotAuthorizedError: user cannot edit this article
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    a = assert_can_publish_article(db, article_id, user)

    # Write self-review to git — the publisher's own review (real name).
    commit_hash = _write_review_to_git(
        article_id, user_id, self_review, comment, user.name, f"{user_id}@peerpedia",
    )

    # Enter sedimentation so scope derivation works.
    a.status = "sedimentation"

    # Cache scores in DB.
    upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=user_id, scores=self_review,
    )

    # Start the sink timer.
    sink_days = (
        params.sink.new_article_default_days
        if a.status == "draft"
        else params.sink.edit_article_default_days
    )
    set_sink_start(db, article_id, sink_days)

    # Recompute score.
    score = compute_article_score(db, article_id)
    a = get_article(db, article_id)
    if score is not None:
        a.score = score

    return {"id": a.id, "title": a.title, "status": a.status}


# ═══════════════════════════════════════════════════════════════════════════════
# Review
# ═══════════════════════════════════════════════════════════════════════════════


def submit_review(
    db: Session,
    article_id: str,
    reviewer_id: str,
    scores: dict,
    commit_hash: str,
    *,
    comment: str = "",
) -> dict:
    """Submit or update a review for an article.

    Git-first: writes review files to git before DB mutation.
    Recomputes article score and author reputations.
    """
    user = get_user(db, reviewer_id)
    if user is None:
        raise NotFoundError("Reviewer not found")

    article = assert_can_submit_review(db, article_id)

    author_ids = get_author_ids(db, article_id)

    if article.status == "sedimentation":
        # Anonymous: derive a stable anonymous ID so the reviewer's identity
        # is not exposed in the git directory structure.  The same
        # (article, reviewer) pair always maps to the same anonymous ID.
        anon_id = _derive_anonymous_id(article_id, reviewer_id)
        display_name = derive_anonymous_name(anon_id)
        email = f"anon-{anon_id}@peerpedia"
        _write_review_to_git(article_id, anon_id, scores, comment, display_name, email)
    else:
        display_name = user.name
        email = f"{reviewer_id}@peerpedia"
        _write_review_to_git(article_id, reviewer_id, scores, comment, display_name, email)

    r = upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=reviewer_id, scores=scores,
    )

    score = compute_article_score(db, article_id)
    if score is not None:
        article.score = score

    for aid in author_ids:
        compute_author_reputation(db, aid)

    return {"review_id": r.id, "scores": r.scores}


def _derive_anonymous_id(article_id: str, reviewer_id: str) -> str:
    """Derive a stable anonymous directory ID for a reviewer+article pair.

    Deterministic — the same inputs always produce the same output, so a
    reviewer's anonymous identity is consistent across multiple reviews of
    the same article.  Different articles get different anonymous IDs.
    """
    seed = f"{article_id}:{reviewer_id}:peerpedia-anon"
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


def _write_review_to_git(
    article_id: str,
    directory_id: str,
    scores: dict,
    comment: str,
    display_name: str,
    email: str,
) -> str:
    """Write review to git: a folder per reviewer with ``scores.json`` and
    a ``threads/`` subdirectory of timestamped Markdown files.

    *directory_id* is the real reviewer_id for published reviews, or a
    derived anonymous ID for sedimentation reviews.

    Returns the new HEAD commit hash.
    """
    import json
    from datetime import datetime, timezone

    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError(f"Article repo not found: {article_id}")

    review_dir = rp / "reviews" / directory_id
    threads_dir = review_dir / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)

    # Scores: always overwrite with latest.
    (review_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    # Comment: create a new numbered thread file.
    if comment:
        existing = sorted(threads_dir.glob("*.md"))
        next_num = len(existing) + 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        thread_path = threads_dir / f"{next_num:03d}.md"
        thread_path.write_text(f"### {display_name} ({ts})\n\n{comment}\n")

    # Lock for commit.
    lock = get_article_lock(article_id)
    acquired = lock.acquire(timeout=10)
    if not acquired:
        raise ConflictError("Article busy — retry later")
    try:
        h = commit_article(rp, f"Review by {display_name}", display_name, email)
    finally:
        lock.release()
    return h


# ═══════════════════════════════════════════════════════════════════════════════
# Merge
# ═══════════════════════════════════════════════════════════════════════════════


def accept_merge(db: Session, article_id: str, proposal_id: str, user_id: str) -> dict:
    """Accept a merge proposal: git merge fork into target, rebuild authors."""
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    mp = get_merge_proposal(db, proposal_id)
    if mp is None:
        raise NotFoundError("Merge proposal not found")
    if mp.target_article_id != article_id:
        raise BadRequestError("Proposal does not belong to this article")
    if user_id not in get_author_ids(db, article_id):
        raise NotAuthorizedError("Only article authors can accept/reject merges")

    target_repo = DEFAULT_ARTICLES_DIR / article_id
    fork_repo = DEFAULT_ARTICLES_DIR / mp.fork_article_id

    if not (target_repo / ".git").is_dir():
        raise NotFoundError(f"Target article repo not found: {article_id}")
    if not (fork_repo / ".git").is_dir():
        raise NotFoundError(f"Fork article repo not found: {mp.fork_article_id}")

    try:
        merge_git_repos(target_repo, fork_repo, user.name)
    except MergeConflictError:
        return {
            "status": "conflict",
            "message": "Merge conflicts detected.",
        }

    rebuild_article_authors(db, article_id)

    mp = accept_merge_proposal(db, proposal_id)
    return {"id": mp.id, "status": mp.status}


# ═══════════════════════════════════════════════════════════════════════════════
# Sync — apply incoming git bundle
# ═══════════════════════════════════════════════════════════════════════════════


def apply_sync_bundle(
    db: Session,
    article_id: str,
    *,
    ff_only: bool = False,
) -> str:
    """Merge fetched bundle objects (``FETCH_HEAD``) and reconcile DB state.

    The caller must have already called ``ingest_bundle`` to verify + fetch
    objects into the repo.  This function only does the merge and DB
    reconciliation.  It does NOT import from ``sync/``.

    Returns the new HEAD commit hash.

    Raises:
        MergeConflictError: merge conflict (ff-only rejected).
    """
    import git

    rp = DEFAULT_ARTICLES_DIR / article_id
    repo = git.Repo(rp)

    merge_args = ["FETCH_HEAD", "--ff-only"] if ff_only else ["FETCH_HEAD"]
    try:
        repo.git.merge(*merge_args)
    except git.GitCommandError as e:
        try:
            repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Merge failed: {e}") from e

    new_head = repo.head.commit.hexsha

    # DB reconciliation — git state changed, DB must follow
    rebuild_article_authors(db, article_id)
    score = compute_article_score(db, article_id)
    if score is not None:
        article = get_article(db, article_id)
        article.score = score

    return new_head
