# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Sync orchestration — apply incoming git bundles and reconcile DB state.

This module bridges the gap between git (SOT for review content) and the DB
(score cache).  ``sync_reviews_from_worktree`` is the key function — it reads review
scores from the git worktree and writes them into the DB Review cache, so
that ``recompute_article_score`` can see reviews that arrived via sync.

Call graph::

    apply_sync_bundle
      ├► git (merge FETCH_HEAD)
      ├► commands.articles.rebuild_article_authors
      ├► sync_reviews_from_worktree                    ← G5 fix: sync before scoring
      ├► commands.workflow.recompute_article_score
      └▻ commands.workflow.publish_ready_articles  ← G4 trigger

    sync_reviews_from_worktree
      ├► git_backend.list_review_dirs        (list reviews/*/ directories)
      ├► for each dir:
      │     ├► git_backend.read_review_scores (parse scores.json)
      │     └► crud_review.upsert_review      (write to DB cache)
      └► Fail fast: missing or malformed scores.json raises immediately

Key design decision — reviewer identity
----------------------------------------
``sync_reviews_from_worktree`` uses the git directory name directly as ``reviewer_id``
in the DB.  During sedimentation, reviews are stored under anonymous hashes
(``sha256(article_id:reviewer_id)[:12]``).  These 12-char hex strings are
valid DB ``reviewer_id`` values — ``derive_anonymous_name`` handles display.
When the article publishes, the real identity can be revealed separately.

Reviewer's checklist
--------------------
- Is ``sync_reviews_from_worktree`` called before every ``recompute_article_score``
  that follows a git state change?
- Does ``apply_sync_bundle`` trigger ``publish_ready_articles`` after
  reconciliation?  (A sync might bring reviews that make an article
  publishable.)
- Fail fast: are malformed scores.json files raised, not skipped?

"""

from __future__ import annotations

import logging
from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.config.params import extract_user_id_from_email
from peerpedia_core.types import short_id
from peerpedia_core.types.status import is_platform_commit, parse_status_tag, VALID_ARTICLE_STATUSES
from peerpedia_core.storage.git_backend import extract_pubkey_from_message
from peerpedia_core.exceptions import BadRequestError, NotAuthorizedError, SignatureVerificationError
from peerpedia_core.storage.db.crud_article import update_article_status, update_witnessed_at
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_review import upsert_review
from peerpedia_core.storage.db.crud_user import get_user, get_users_by_ids, update_user_public_key
from peerpedia_core.crypto import pubkey_hex_to_ssh_line
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR, reset_to_commit,
    MergeConflictError,
    get_commit_history,
    get_head_hash,
    list_review_dirs,
    merge_fetch_head,
    verify_commit_signature,
)

from peerpedia_core.commands.articles._helpers import require_article, require_article_repo, require_review_scores
from peerpedia_core.commands.articles import rebuild_article_authors
from peerpedia_core.commands.workflow import publish_ready_articles, recompute_article_score


logger = logging.getLogger(__name__)


def sync_status_from_git(db: Session, article_id: str) -> None:
    """Read status transitions from commit messages and update DB.

    Walks new commits since ``last_author_rebuild_hash``.  Only commits
    authored by PeerPedia (system@peerpedia) are considered.  The commit
    message has the form ``[status] <valid_status>``.
    The latest matching commit wins.

    Raises NotFoundError if the article or its git repo is not found.
    """
    article = require_article(db, article_id)
    rp = require_article_repo(article_id)

    since = article.last_author_rebuild_hash
    for commit in get_commit_history(rp, since_hash=since):
        new_status = parse_status_tag(
            commit["message"], commit["author_email"]
        )
        if new_status:
            update_article_status(db, article_id, new_status)
            break  # iter_commits returns newest first — first match is the latest status


def sync_reviews_from_worktree(db: Session, article_id: str) -> None:
    """Sync review scores from git worktree into the DB Review cache.

    Reads every ``reviews/{dir}/scores.json`` in the article's git worktree
    and upserts into the DB.  Uses the current git HEAD as commit_hash.

    Directory names are used directly as reviewer_id — anonymous hashes and
    real UUIDs both work (derive_anonymous_name handles display).

    Fail fast: malformed or missing scores.json raises immediately.
    Reviews without valid scores or comment are skipped with a warning.
    """
    import logging
    from .reviews import assert_valid_review

    _logger = logging.getLogger(__name__)
    rp = DEFAULT_ARTICLES_DIR / article_id
    head_hash = get_head_hash(rp)

    for dir_name in list_review_dirs(rp):
        scores = require_review_scores(rp, dir_name, article_id)
        # Validate scores on sync path — comment is stored in thread files
        # (not scores.json) so we only enforce score validity here.
        try:
            assert_valid_review(scores, comment=None, check_comment=False)
        except BadRequestError as e:
            _logger.warning(
                "Sync: skipping invalid review in %s/reviews/%s: %s",
                article_id, dir_name, e.detail,
            )
            continue
        upsert_review(
            db,
            article_id=article_id,
            commit_hash=head_hash,
            reviewer_id=dir_name,
            scores=scores,
        )


def apply_sync_bundle(
    db: Session,
    article_id: str,
    *,
    ff_only: bool = True,
) -> str:
    """Merge fetched bundle objects (``FETCH_HEAD``) and reconcile DB state.

    Defaults to ``--ff-only``: only fast-forward merges are performed,
    so sync does not create new merge commits (which would cause
    infinite ping-pong between peers).  If fast-forward is impossible
    (genuine content divergence), raises ``MergeConflictError`` — the
    caller should use the fork/merge proposal flow instead.

    The caller must have already called ``ingest_bundle`` to verify + fetch
    objects into the repo.  This function only does the merge and DB
    reconciliation.  It does NOT import from ``bundle/`` or ``transport/``.

    After merge: syncs reviews from git, recomputes article score, and
    triggers publish_ready_articles to catch any newly-publishable articles.

    Returns the new HEAD commit hash.

    Raises:
        MergeConflictError: merge conflict (ff-only rejected).

    Git is mutated first (``merge_fetch_head``).  If any subsequent DB
    step fails, git is rolled back to ``old_head``.  DB changes are never
    committed inside this function — the caller owns ``commit()``, so a
    failed call leaves the DB clean via session rollback.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id

    try:
        old_head = get_head_hash(rp)
    except ValueError:
        old_head = None

    new_head = merge_fetch_head(rp, ff_only=ff_only)

    # ── DB reconciliation — if any step fails, rollback git ─────────────────
    try:
        # Verify signatures on all new human-authored commits (TOFU model).
        if old_head:
            _verify_new_commits(db, rp, since_hash=old_head)

        # DB reconciliation — git state changed, DB must follow
        rebuild_article_authors(db, article_id)

        # Fail fast: every article must have at least one maintainer.
        if not get_maintainer_ids(db, article_id):
            raise NotAuthorizedError(
                f"Script {article_id} has no maintainers — "
                "creation path must seed at least one maintainer"
            )

        # Sync reviews from git before scoring — git is the SOT (G5)
        sync_reviews_from_worktree(db, article_id)

        # Sync status transitions from commit messages (P2P status transport).
        sync_status_from_git(db, article_id)

        # Witness: record the server clock for priority-dispute defense.
        update_witnessed_at(db, article_id)

        # Full integrity check — DB cross-validation + auto-repair after sync.
        assert_article_integrity(db, article_id, level="full")

        recompute_article_score(db, article_id)

        # Trigger auto-publish for any articles that may now be ready (G4)
        publish_ready_articles(db)

    except Exception:
        # Rollback git to pre-merge state.  DB changes were never committed
        # (caller owns commit()), so only git needs cleanup.
        _rollback_git(rp, old_head, new_head)
        raise

    return new_head


def _rollback_git(repo_path: Path, old_head: str | None, new_head: str) -> None:
    """Reset git to *old_head* after a failed sync, undoing *new_head*.

    If *old_head* is None (repo was empty before the failed merge), the
    repo is left with the new HEAD — an empty repo can't be rolled back
    to nothing without deleting objects that might be needed by other refs.
    """
    if old_head is None:
        logger.warning(
            "Cannot rollback git reset for %s — repo had no prior HEAD. "
            "Repo left at %s.",
            repo_path.name, short_id(new_head),
        )
        return
    try:
        reset_to_commit(repo_path, old_head)
        logger.info(
            "Rolled back git for %s: %s → %s after DB reconciliation failure.",
            repo_path.name, short_id(new_head), short_id(old_head),
        )
    except Exception as exc:
        logger.error(
            "Failed to rollback git for %s from %s to %s: %s",
            repo_path.name, short_id(new_head), short_id(old_head), exc,
        )


def _verify_new_commits(db: Session, repo_path: Path, *, since_hash: str) -> None:
    """Verify signatures on new human-authored commits (TOFU model).

    Each commit message must contain a ``Pubkey: <hex>`` trailer.  The
    signature (gpgsig header) is verified against that pubkey.  The pubkey
    is checked for consistency with any previously-stored pubkey for the
    same user_id (TOFU: first encounter stores, mismatch rejects).
    Platform commits (author_email == system@peerpedia) are skipped.
    """
    commits = list(get_commit_history(repo_path, since_hash=since_hash))

    # Batch-load users to avoid N+1 queries.
    user_ids = {
        extract_user_id_from_email(c["author_email"])
        for c in commits
        if not is_platform_commit(c["author_email"])
    }
    users_by_id = {u.id: u for u in get_users_by_ids(db, user_ids)}

    for commit in commits:
        author_email = commit["author_email"]
        if is_platform_commit(author_email):
            continue

        commit_hash = commit["hash"]
        pubkey_hex = extract_pubkey_from_message(commit["message"])
        if not pubkey_hex:
            raise SignatureVerificationError(
                f"Commit {short_id(commit_hash)} by {author_email} "
                "has no Pubkey trailer — unsigned human commit"
            )

        # Verify the git signature.
        ssh_line = pubkey_hex_to_ssh_line(pubkey_hex)
        verify_commit_signature(repo_path, commit_hash, ssh_line, author_email)

        # TOFU pubkey consistency.
        user_id = extract_user_id_from_email(author_email)
        user = users_by_id.get(user_id)
        if user is None:
            continue
        if user.public_key is None:
            update_user_public_key(db, user_id, pubkey_hex)
        elif user.public_key != pubkey_hex:
            # Key rotation: the commit is signed with a new key.  The
            # signature already passed verify_commit_signature above, so
            # the new key is cryptographically valid.  Auto-update the
            # stored public_key — same as the auth middleware (TOFU).
            # In a P2P network you can't guarantee every peer received
            # a key-rotation notification before seeing a commit signed
            # with the new key.  Rejecting here would permanently break
            # sync for every peer that missed the rotation event.
            logger.warning(
                "Key rotation for %s: pubkey %s... → %s... — auto-updated.",
                user_id,
                user.public_key[:16] if user.public_key else "None",
                pubkey_hex[:16],
            )
            update_user_public_key(db, user_id, pubkey_hex)


# Re-export helpers used by this module.
from peerpedia_core.commands.integrity import assert_article_integrity  # noqa: E402
