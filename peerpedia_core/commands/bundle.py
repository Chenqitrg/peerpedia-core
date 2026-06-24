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

from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.config.params import EMAIL_SUFFIX, PLATFORM_EMAIL
from peerpedia_core.exceptions import NotAuthorizedError, SignatureVerificationError
from peerpedia_core.storage.db.crud_article import get_article, update_article_status, update_witnessed_at
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_review import upsert_review
from peerpedia_core.storage.db.crud_user import get_user, get_users_by_ids, update_user_public_key
from peerpedia_core.crypto import pubkey_hex_to_ssh_line
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    MergeConflictError,
    get_commit_history,
    get_head_hash,
    list_review_dirs,
    merge_fetch_head,
    read_review_scores,
    verify_commit_signature,
)

from peerpedia_core.commands.articles import rebuild_article_authors
from peerpedia_core.commands.workflow import publish_ready_articles, recompute_article_score


_PLATFORM_EMAIL = PLATFORM_EMAIL
_VALID_STATUSES = {"draft", "sedimentation", "published"}


def _parse_status_tag(message: str, author_email: str) -> str | None:
    """Return the article status if *message* is a valid platform status commit.

    Only accepts commits authored by the PeerPedia platform (system@peerpedia)
    whose message has the form ``[status] <valid_status>``.
    """
    if author_email != _PLATFORM_EMAIL:
        return None
    msg = message.strip()
    prefix = "[status] "
    if not msg.startswith(prefix):
        return None
    status = msg[len(prefix):]
    return status if status in _VALID_STATUSES else None


def sync_status_from_git(db: Session, article_id: str) -> None:
    """Read status transitions from commit messages and update DB.

    Walks new commits since ``last_author_rebuild_hash``.  Only commits
    authored by PeerPedia (system@peerpedia) are considered.  The commit
    message has the form ``[status] <valid_status>``.
    The latest matching commit wins.
    """
    article = get_article(db, article_id)
    if article is None:
        raise FileNotFoundError(f"Article not found: {article_id}")

    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found for article: {article_id}")

    since = article.last_author_rebuild_hash
    for commit in get_commit_history(rp, since_hash=since):
        new_status = _parse_status_tag(
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
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    head_hash = get_head_hash(rp)

    for dir_name in list_review_dirs(rp):
        scores = read_review_scores(rp, dir_name)
        if scores is None:
            raise FileNotFoundError(
                f"scores.json not found in reviews/{dir_name}/ for article {article_id}"
            )
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
    """
    rp = DEFAULT_ARTICLES_DIR / article_id

    try:
        old_head = get_head_hash(rp)
    except ValueError:
        old_head = None

    new_head = merge_fetch_head(rp, ff_only=ff_only)

    # Verify signatures on all new human-authored commits (TOFU model).
    if old_head:
        _verify_new_commits(db, rp, since_hash=old_head)

    # DB reconciliation — git state changed, DB must follow
    rebuild_article_authors(db, article_id)

    # Fail fast: every article must have at least one maintainer.
    # If this fires, the article creation path (POST /articles handler)
    # did not seed ScriptMaintainer rows — fix it there, not here.
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
    # When new commits arrive via sync, the server attests "this commit
    # existed by this UTC time."  Combined with the git DAG topology,
    # this bounds the commit's true creation window.
    update_witnessed_at(db, article_id)

    # TODO(social-graph): ``sync discover`` — traverse the social graph to
    # find new peers and articles.  Follows, unfollows, and bookmarks are
    # pushed to the server via _push_social() after local commit.  What's
    # missing is the discovery side: given a seed peer, walk the graph
    # (who follows whom, who bookmarks what) to surface new content.

    # Full integrity check — DB cross-validation + auto-repair after sync.
    assert_article_integrity(db, article_id, level="full")

    recompute_article_score(db, article_id)

    # Trigger auto-publish for any articles that may now be ready (G4)
    publish_ready_articles(db)

    return new_head


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
        _extract_user_id_from_email(c["author_email"])
        for c in commits
        if c["author_email"] != _PLATFORM_EMAIL
    }
    users_by_id = {u.id: u for u in get_users_by_ids(db, user_ids)}

    for commit in commits:
        author_email = commit["author_email"]
        if author_email == _PLATFORM_EMAIL:
            continue

        commit_hash = commit["hash"]
        pubkey_hex = _extract_pubkey_from_message(commit["message"])
        if not pubkey_hex:
            raise SignatureVerificationError(
                f"Commit {commit_hash[:8]} by {author_email} "
                "has no Pubkey trailer — unsigned human commit"
            )

        # Verify the git signature.
        ssh_line = pubkey_hex_to_ssh_line(pubkey_hex)
        verify_commit_signature(repo_path, commit_hash, ssh_line, author_email)

        # TOFU pubkey consistency.
        user_id = _extract_user_id_from_email(author_email)
        user = users_by_id.get(user_id)
        if user is None:
            continue
        if user.public_key is None:
            update_user_public_key(db, user_id, pubkey_hex)
        elif user.public_key != pubkey_hex:
            # TODO(key-rotation-notify): key rotation is compatible with
            # TOFU only if the key owner notifies peers to update before
            # pushing new commits.  Currently there is no protocol for this
            # — no push_key_rotation endpoint, no gossip.  When a user
            # rotates, peers hit this error with no recovery path.
            raise SignatureVerificationError(
                f"Pubkey mismatch for {user_id}: "
                f"expected {user.public_key[:16]}..., "
                f"got {pubkey_hex[:16]}..."
            )


# Re-export integrity helpers and functions used by this module.
from peerpedia_core.commands.integrity import (  # noqa: E402
    _extract_human_authors_from_git,
    _extract_pubkey_from_message,
    _extract_user_id_from_email,
    assert_article_integrity,
)
