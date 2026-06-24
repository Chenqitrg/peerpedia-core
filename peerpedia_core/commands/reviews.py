# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Review orchestration — submit reviews and write review files to git.

TODO(review-feedback): after a review, the reviewer should be notified when
the article publishes (outcome feedback loop).  Currently a reviewer writes
a review and never learns whether their input mattered.

TODO(author-rebuttal): after receiving reviews, the author should be able to
write a formal rebuttal — a structured point-by-point response to each review,
stored in the git repo under the reviewer's directory (reviews/{id}/threads/).
This is standard in academic peer review: author responds, reviewers discuss,
editor decides.  Currently the review is one-way and final — no author
response path exists.

Call graph::

    submit_review
      ├► policies.assert_can_submit_review     (sedimentation or published)
      ├► write_review_to_git                  (git-first: scores.json + threads/*.md)
      │     ├► git_backend.commit_article      (returns commit_hash)
      │     └► storage.locks.get_article_lock  (serialize concurrent git writes)
      ├► crud_review.upsert_review             (DB cache, uses commit_hash from git)
      ├► commands.workflow.recompute_article_score
      └► commands.workflow.recompute_author_reputation  (for each author)

    _derive_anonymous_id
      └► sha256(article_id:reviewer_id)[:12]   (deterministic, stable per article)

    write_review_to_git
      ├► Write reviews/{directory_id}/scores.json  (overwrite latest)
      ├► Write reviews/{directory_id}/threads/{nnn}.md  (append new file)
      └► git_backend.commit_article

Key design — anonymity during sedimentation
--------------------------------------------
When the article is in sedimentation, the git directory uses an anonymous
hash (``_derive_anonymous_id``) so reviewer identities are not exposed in
the git filesystem.  The DB stores the real ``reviewer_id`` from the caller.
The anonymous directory name and the real DB ``reviewer_id`` are linked only
through the commit — when the article publishes, the mapping can be resolved.

    sedimentation review:   git dir = anon_hash    DB reviewer_id = real UUID
    published review:       git dir = real UUID     DB reviewer_id = real UUID

Reviewer's checklist
--------------------
- Is ``write_review_to_git`` called before ``upsert_review``?  (git-first)
- Is ``commit_hash`` taken from the return value of ``write_review_to_git``,
  not from an external parameter?  (previous bug)
- Are author reputations recomputed for every author after score changes?
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.exceptions import ConflictError, NotFoundError
from peerpedia_core.policies.articles import assert_can_submit_review
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.crud_review import get_reviews_for_article as _get, upsert_review
from peerpedia_core.storage.db.crud_user import derive_anonymous_name, get_user
from peerpedia_core.crypto import write_key_to_tempfile
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, commit_article
from peerpedia_core.storage.locks import get_article_lock
from peerpedia_core.commands.workflow import recompute_article_score, recompute_author_reputation


def submit_review(
    db: Session,
    article_id: str,
    reviewer_id: str,
    scores: dict,
    *,
    comment: str = "",
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Submit or update a review for an article.

    Git-first: writes review files to git before DB mutation.
    Recomputes article score and author reputations.
    The commit_hash for the DB cache is taken from the new git commit.

    If *signing_key_bytes* and *pubkey_hex* are provided, the review commit
    is signed via SSH and the pubkey is embedded.
    """
    user = get_user(db, reviewer_id)
    if user is None:
        raise NotFoundError("Reviewer not found")

    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    assert_can_submit_review(article)

    author_ids = get_author_ids(db, article_id)

    if article.status == "sedimentation":
        anon_id = _derive_anonymous_id(article_id, reviewer_id)
        display_name = derive_anonymous_name(anon_id)
        email = f"anon-{anon_id}@peerpedia"
        commit_hash = write_review_to_git(
            article_id, anon_id, scores, comment, display_name, email,
            signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
        )
    else:
        display_name = user.name
        email = f"{reviewer_id}@peerpedia"
        commit_hash = write_review_to_git(
            article_id, reviewer_id, scores, comment, display_name, email,
            signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
        )

    r = upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=reviewer_id, scores=scores, comment=comment,
    )

    recompute_article_score(db, article_id)

    for aid in author_ids:
        recompute_author_reputation(db, aid)

    # TODO(author-reply): authors cannot reply to reviews.  The reply should
    # be written to the reviewer's directory in the git repo (e.g.
    # reviews/{anon_id}/threads/{timestamp}-reply.md), forming a complete
    # conversation record.  The old system had a Review.thread field and a
    # POST .../reviews/{id}/messages endpoint for this.
    #
    # TODO(review-update): reviews are immutable after submission.  Reviewers
    # cannot correct scores or update comments if they discover an error.

    return {"review_id": r.id, "scores": r.scores, "commit_hash": commit_hash}


def _derive_anonymous_id(article_id: str, reviewer_id: str) -> str:
    """Derive a stable anonymous directory ID for a reviewer+article pair.

    Deterministic — the same inputs always produce the same output, so a
    reviewer's anonymous identity is consistent across multiple reviews of
    the same article.  Different articles get different anonymous IDs.
    """
    seed = f"{article_id}:{reviewer_id}:peerpedia-anon"
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


def write_review_to_git(
    article_id: str,
    directory_id: str,
    scores: dict,
    comment: str,
    display_name: str,
    email: str,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> str:
    """Write review to git: a folder per reviewer with ``scores.json`` and
    a ``threads/`` subdirectory of timestamped Markdown files.

    *directory_id* is the real reviewer_id for published reviews, or a
    derived anonymous ID for sedimentation reviews.

    Returns the new HEAD commit hash.
    """
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
        key_path = write_key_to_tempfile(signing_key_bytes) if signing_key_bytes else None
        try:
            h = commit_article(
                rp, f"[review] {display_name}", display_name, email,
                signing_key=key_path, pubkey_hex=pubkey_hex,
            )
        finally:
            if key_path:
                key_path.unlink(missing_ok=True)
    finally:
        lock.release()
    return h


# ── Read wrapper ──────────────────────────────────────────────────────────


def get_reviews_for_article(db: Session, article_id: str) -> list:
    """Return all cached reviews for an article, newest first."""
    return _get(db, article_id)
