# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article orchestration commands.

Each function combines core primitives (CRUD, git, policies, workflow) into
a single business operation.  Callers (CLI, backend routes) own the transaction
boundary — these functions do NOT call ``db.commit()``.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import git as gitmod
from sqlalchemy.orm import Session

from peerpedia_core.config.params import params

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.policies.articles import (
    assert_can_edit_article,
    assert_can_fork_article,
    assert_can_rollback_article,
)
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article,
    get_author_ids,
    increment_fork_count,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_article_authors import (
    get_authors_from_git,
    rebuild_article_authors,
)
from peerpedia_core.storage.db.crud_merge import (
    accept_merge_proposal,
    get_merge_proposal,
)
from peerpedia_core.storage.db.crud_review import (
    get_review_by_user_scope,
    upsert_review,
)
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    MergeConflictError,
    commit_article,
    get_article_lock,
    get_commit_history,
    init_article_repo,
    merge_git_repos,
)
from peerpedia_core.workflow.reputation import compute_author_reputation
from peerpedia_core.workflow.scoring import compute_article_score_for_commit


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

    if (src / ".git").is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        init_article_repo(fork_id)

    fork = create_article(
        db,
        id=fork_id,
        title=original.title,
        abstract=original.abstract,
        keywords=original.keywords,
        categories=original.categories,
        authors=[user_id],
        status="draft",
        forked_from=article_id,
    )
    increment_fork_count(db, article_id)

    if (dst / ".git").is_dir():
        git_authors = get_authors_from_git(dst, db)
        git_authors.add(user_id)
        rebuild_article_authors(db, fork_id, git_authors)

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
    repo.commit(target_hash)
    repo.git.checkout(target_hash, "--", ".")

    new_hash = commit_article(
        rp, f"Rollback to {target_hash[:8]}", "System", "system@peerpedia",
    )
    set_sink_start(db, article_id, params.sink.edit_article_default_days)

    author_ids = get_author_ids(db, article_id)
    upsert_review(
        db,
        article_id=article_id,
        commit_hash=new_hash,
        reviewer_id=author_ids[0] if author_ids else "system",
        scope="pool",
        scores={"originality": 0, "rigor": 0, "completeness": 0, "pedagogy": 0, "impact": 0},
    )
    score = compute_article_score_for_commit(db, article_id, new_hash)
    if score is not None:
        article.score = score

    return {"commit_hash": new_hash, "message": f"Rollback to {target_hash[:8]}"}


# ═══════════════════════════════════════════════════════════════════════════════
# Create
# ═══════════════════════════════════════════════════════════════════════════════


def create_article_with_content(
    db: Session,
    *,
    title: str,
    content: str,
    format: str = "markdown",
    user_id: str,
    author_ids: list[str] | None = None,
    publish: bool = False,
    self_review: dict | None = None,
    abstract: str | None = None,
    keywords: str | None = None,
    categories: str | None = None,
    article_id: str | None = None,
) -> dict:
    """Create an article with content committed to git.

    Returns:
        {"id": <article_id>, "title": ..., "status": ..., "commit_hash": ...}

    Raises:
        NotFoundError: author not found in DB
        BadRequestError: publish requested without self_review
    """
    if not title.strip():
        raise BadRequestError("Title is required")

    authors = author_ids or [user_id]
    for aid in authors:
        if get_user(db, aid) is None:
            raise NotFoundError(f"Author '{aid}' not found")

    if publish and self_review is None:
        raise BadRequestError("self_review is required when publishing")

    # Validate client-generated ID if provided
    if article_id is not None:
        try:
            uuid.UUID(article_id)
        except ValueError:
            raise BadRequestError(f"Invalid article ID: {article_id}")
        if get_article(db, article_id) is not None:
            raise ConflictError(f"Article '{article_id}' already exists")

    a = create_article(
        db,
        id=article_id or str(uuid.uuid4()),
        title=title,
        abstract=abstract or "",
        keywords=keywords or "",
        categories=categories or "",
        authors=authors,
        status="draft",
    )

    rp = DEFAULT_ARTICLES_DIR / a.id
    is_new = not (rp / ".git").is_dir()
    if is_new:
        init_article_repo(a.id)

    ext = ".typ" if format == "typst" else ".md"
    (rp / f"article{ext}").write_text(content)
    author_name = authors[0]
    commit_hash = commit_article(
        rp, "Initial submission", author_name, f"{authors[0]}@peerpedia",
        allow_empty=True,
    )

    rebuild_article_authors(db, a.id, set(authors))

    if self_review is not None:
        upsert_review(
            db, article_id=a.id, commit_hash=commit_hash,
            reviewer_id=authors[0], scope="pool", scores=self_review,
        )
        score = compute_article_score_for_commit(db, a.id, commit_hash)
        if score is not None:
            a.score = score

    if publish:
        set_sink_start(db, a.id, params.sink.new_article_default_days)

    return {
        "id": a.id, "title": a.title, "status": a.status,
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
    publish: bool = False,
    self_review: dict | None = None,
    user_id: str,
) -> dict:
    """Edit an article: update content/metadata, commit to git, optionally re-enter pool.

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

    if publish and self_review is None:
        raise BadRequestError("self_review is required when publishing")

    author_ids = get_author_ids(db, article_id)
    author = author_ids[0] if author_ids else "unknown"

    if content is not None:
        ext = ".md"
        for e in [".md", ".typ"]:
            if (rp / f"article{e}").exists():
                ext = e
                break
        (rp / f"article{ext}").write_text(content)

    if title is not None:
        a.title = title
    if abstract is not None:
        a.abstract = abstract
    if keywords is not None:
        a.keywords = keywords
    if categories is not None:
        a.categories = categories

    if content is not None:
        commit_hash = commit_article(rp, "Edit: content updated", author, f"{author}@peerpedia")
    else:
        repo = gitmod.Repo(rp)
        commit_hash = repo.head.commit.hexsha if repo.head.is_valid() else None

    git_authors = get_authors_from_git(rp, db, since_hash=a.last_author_rebuild_hash)
    rebuild_article_authors(db, article_id, git_authors)

    if publish:
        sink_days = (
            params.sink.new_article_default_days
            if a.status == "draft"
            else params.sink.edit_article_default_days
        )
        set_sink_start(db, article_id, sink_days)

        if self_review is not None:
            upsert_review(
                db, article_id=a.id, commit_hash=commit_hash,
                reviewer_id=author, scope="pool", scores=self_review,
            )
        score = compute_article_score_for_commit(db, a.id, commit_hash)
        if score is not None:
            a.score = score

    return {
        "id": a.id, "title": a.title, "status": a.status,
        "commit_hash": commit_hash,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Review
# ═══════════════════════════════════════════════════════════════════════════════


def submit_review(
    db: Session,
    article_id: str,
    reviewer_id: str,
    scores: dict,
    scope: str,
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

    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")

    if scope == "pool" and article.status not in ("sedimentation", "draft"):
        existing_pool = get_review_by_user_scope(
            db, article_id, reviewer_id, "pool", commit_hash=commit_hash,
        )
        if existing_pool:
            raise ConflictError(
                "Pool reviews are frozen after the article leaves the sedimentation pool."
            )

    author_ids = get_author_ids(db, article_id)

    _write_review_to_git(article_id, reviewer_id, scores, comment, user, article.status)

    r = upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=reviewer_id, scope=scope, scores=scores,
    )

    rp = DEFAULT_ARTICLES_DIR / article_id
    if (rp / ".git").is_dir():
        commits = get_commit_history(rp)
        if commits:
            score = compute_article_score_for_commit(db, article_id, commits[0]["hash"])
            if score is not None:
                article.score = score

    for aid in author_ids:
        compute_author_reputation(db, aid)

    return {"review_id": r.id, "scores": r.scores}


def _write_review_to_git(
    article_id: str,
    reviewer_id: str,
    scores: dict,
    comment: str,
    reviewer,
    article_status: str,
) -> None:
    """Write review files to git repo (git-first principle)."""
    import json
    from datetime import datetime, timezone

    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return

    review_dir = rp / "reviews" / reviewer_id
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    if comment:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        display_name = reviewer.name or reviewer.username
        thread_path = review_dir / "thread.md"
        existing = thread_path.read_text() if thread_path.exists() else ""
        thread_path.write_text(existing + f"### {display_name} ({ts})\n\n{comment}\n\n")

    lock = get_article_lock(article_id)
    acquired = lock.acquire(timeout=10)
    if not acquired:
        raise ConflictError("Article busy — retry later")
    try:
        display_name = reviewer.name or reviewer.username
        commit_article(rp, f"Review by {display_name}", display_name, f"{reviewer_id}@peerpedia")
    finally:
        lock.release()


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

    if not (target_repo / ".git").is_dir() or not (fork_repo / ".git").is_dir():
        mp = accept_merge_proposal(db, proposal_id)
        return {"id": mp.id, "status": mp.status}

    try:
        merge_git_repos(target_repo, fork_repo, user.name or user.username)
    except MergeConflictError:
        return {
            "status": "conflict",
            "message": "Merge conflicts detected.",
        }

    all_authors = get_authors_from_git(target_repo, db)
    rebuild_article_authors(db, article_id, all_authors)

    mp = accept_merge_proposal(db, proposal_id)
    return {"id": mp.id, "status": mp.status}
