# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Workflow orchestration — DB-aware wrappers around pure workflow/ functions.

Each function here follows the same pattern: (1) gather data from DB,
(2) call a pure function in ``peerpedia_core.workflow.*``, (3) write the
result back to DB.  None of these functions call ``session.commit()`` —
that is the caller's responsibility.

Call graph::

    publish_ready_articles
      ├► prereq: caller calls commands.sync_reviews_from_worktree()
      ├► DB: query Article.status == "sedimentation"
      ├► for each ready article:
      │     ├► recompute_article_score
      │     ├► workflow.sedimentation.apply_no_review_penalty
      │     └► article.status = "published"
      ├► for each affected author:
      │     └► recompute_author_reputation
      └► returns count (caller is responsible for db.commit())

    recompute_article_score
      ├► DB: get_article, get_reviews_for_article, get_author_ids
      ├► DB: batch-load User rows for reviewer weights
      ├► workflow.scoring.aggregate_review_scores   (pure, with scope_weights)
      └► article.score = result

    recompute_author_reputation
      ├► DB: session.get(User, user_id)  → ValueError if missing
      ├► DB: get_articles_by_author
      ├► workflow.reputation.compute_reputation     (pure)
      ├► workflow.reputation.blend_reputation       (pure, EMA)
      └► crud_user.update_user_reputation

    recalculate_all_reputations
      └► recompute_author_reputation for every user

Reviewer's checklist
--------------------
- Is the two-phase commit in publish_ready_articles correct?
  Phase 1 (status) must succeed before Phase 2 (reputation) runs.
- Does every functions raise on missing data rather than returning a default?
  (e.g. recompute_author_reputation raises ValueError for unknown user)
- Are scope_weights correctly passed from params to aggregate_review_scores?
"""

from __future__ import annotations

from datetime import timedelta, timezone

from peerpedia_core.storage.db import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import get_article, get_articles_by_author, get_author_ids, get_author_ids_batch, list_articles, update_article_score, update_article_status
from peerpedia_core.storage.db.crud_review import get_reviews_for_article, upsert_review
from peerpedia_core.storage.db.crud_user import get_user, get_users_by_ids, list_users, update_user_reputation
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, commit_article, commit_status_marker
from peerpedia_core.types.scores import FiveDimScores, ReputationScores
from peerpedia_core.workflow.reputation import (
    blend_reputation,
    compute_reputation,
    get_reviewer_weight,
)
from peerpedia_core.workflow.scoring import aggregate_review_scores
from peerpedia_core.workflow.sedimentation import apply_no_review_penalty, is_ready_to_publish
from peerpedia_core.workflow.state import (
    ArticleSnapshot,
    ReputationState,
    ReviewSnapshot,
    UserSnapshot,
)


def publish_ready_articles(db: Session) -> int:
    """Scan all articles in sedimentation, publish/reject those whose sink time has elapsed.

    Review gate: at least *min_approvals* community reviewers must approve
    (average score ≥ *approval_score_threshold*).  If not enough approvals,
    the sink is extended up to *max_total_sink_days*; after that the article
    is rejected.

    Returns the number of articles whose status changed in this call
    (published + rejected).
    """
    articles = list_articles(db, status="sedimentation")

    changed_count = 0
    all_author_ids: set[str] = set()

    for article in articles:
        if article.sink_start is None:
            continue

        st = article.sink_start
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        eta = st + timedelta(days=article.sink_duration_days)

        if not is_ready_to_publish(eta):
            continue

        all_reviews = get_reviews_for_article(db, article.id)
        authors = get_author_ids(db, article.id)
        community_reviews = [r for r in all_reviews if r.reviewer_id not in authors]

        # Count approvals: each reviewer's latest score avg ≥ threshold
        approval_count = 0
        for r in community_reviews:
            if r.scores and isinstance(r.scores, dict):
                vals = [v for v in r.scores.values() if isinstance(v, (int, float))]
                if vals and sum(vals) / len(vals) >= params.sink.approval_score_threshold:
                    approval_count += 1

        rp = DEFAULT_ARTICLES_DIR / article.id
        has_repo = (rp / ".git").is_dir()

        if approval_count >= params.sink.min_approvals:
            # Publish: enough reviewers approved.
            score = recompute_article_score(db, article.id)
            if score is None:
                score = apply_no_review_penalty(FiveDimScores().to_dict())
            if has_repo:
                commit_status_marker(rp, "published")
            update_article_status(db, article.id, "published")
            update_article_score(db, article.id, score)
        else:
            # Not enough approvals — extend or reject.
            extra = params.sink.review_deficit_extend_days
            if article.total_sink_days_accumulated + extra <= params.sink.max_total_sink_days:
                # Extend: add days to sink, keep in sedimentation.
                article.sink_duration_days += extra
                article.total_sink_days_accumulated += extra
                article.sink_extended_count += 1
            else:
                # Reject: no more extensions available.
                if has_repo:
                    commit_status_marker(rp, "rejected")
                update_article_status(db, article.id, "rejected")

        for author_id in authors:
            all_author_ids.add(author_id)

        changed_count += 1

    if changed_count == 0:
        return 0

    for author_id in all_author_ids:
        recompute_author_reputation(db, author_id)

    return changed_count


def recompute_article_score(db: Session, article_id: str) -> dict | None:
    """Compute the article score from all cached reviews and write it to DB.

    Returns the computed score dict, or None if no reviews exist.
    Raises ValueError if the article does not exist.
    """
    article = get_article(db, article_id)
    if article is None:
        raise ValueError(f"Article not found: {article_id}")

    all_reviews = get_reviews_for_article(db, article_id)
    if not all_reviews:
        return None

    authors = get_author_ids(db, article_id)
    # Batch-load all reviewer users in one query
    reviewer_ids = {r.reviewer_id for r in all_reviews}
    reviewer_users = get_users_by_ids(db, reviewer_ids)

    user_weight_map: dict[str, float] = {}
    for u in reviewer_users:
        user_weight_map[u.id] = get_reviewer_weight(u.reputation if u.reputation else None)

    review_dicts = []
    reviewer_weights: dict[str, float] = {}
    for r in all_reviews:
        review_dicts.append({
            "scores": r.scores,
            "is_self": r.reviewer_id in authors,
            "reviewer_id": r.reviewer_id,
            "scope": r.scope,
        })
        reviewer_weights[r.reviewer_id] = user_weight_map.get(r.reviewer_id, 1.0)

    scope_weights = {
        "sedimentation": params.score.sedimentation_scope_weight,
        "published": params.score.published_scope_weight,
    }

    score = aggregate_review_scores(review_dicts, reviewer_weights, scope_weights)
    if score is not None:
        update_article_score(db, article.id, score)
    return score


def extract_state(db: Session, user_id: str) -> ReputationState:
    """Build an immutable snapshot of the data needed to compute reputation.

    This is the ONLY place where reputation computation touches the database.
    All pure-algorithm functions consume ``ReputationState`` — never a Session.
    """
    user = get_user(db, user_id)
    if user is None:
        raise ValueError(f"User not found: {user_id}")

    # Gather all articles by this user (needed for compute_reputation).
    articles = get_articles_by_author(db, user_id)
    article_ids = {a.id for a in articles}
    article_map: dict[str, ArticleSnapshot] = {}
    reviews_map: dict[str, tuple[ReviewSnapshot, ...]] = {}

    article_id_list = [a.id for a in articles]
    author_map = get_author_ids_batch(db, article_id_list)

    for a in articles:
        authors = author_map.get(a.id, [])
        all_reviews = get_reviews_for_article(db, a.id)
        review_count = len(all_reviews)

        article_map[a.id] = ArticleSnapshot(
            id=a.id,
            score=a.score,
            status=a.status,
            author_ids=tuple(authors),
            review_count=review_count,
        )

        reviews_map[a.id] = tuple(
            ReviewSnapshot(
                reviewer_id=r.reviewer_id,
                scores=r.scores,
                is_self=r.reviewer_id in authors,
                scope=r.scope,
            )
            for r in all_reviews
        )

    # Gather user snapshots (author + reviewer reputations for weighting).
    reviewer_ids: set[str] = set()
    for revs in reviews_map.values():
        for r in revs:
            reviewer_ids.add(r.reviewer_id)
    all_user_ids = {user_id} | reviewer_ids
    user_rows = get_users_by_ids(db, all_user_ids)
    user_map = {
        u.id: UserSnapshot(id=u.id, reputation=u.reputation if u.reputation else None)
        for u in user_rows
    }

    return ReputationState(
        articles=article_map,
        reviews=reviews_map,
        users=user_map,
    )


def recompute_author_reputation(db: Session, user_id: str, *, user=None) -> ReputationScores:
    """Compute and persist a blended reputation for *user_id*.

    Pass *user* to avoid a re-fetch when the caller already has the User
    object (e.g. ``recalculate_all_reputations`` already called ``list_users``).

    Raises ValueError if the user does not exist.
    """
    if user is None:
        user = get_user(db, user_id)
    if user is None:
        raise ValueError(f"User not found: {user_id}")

    state = extract_state(db, user_id)
    new_rep = compute_reputation(state, user_id)
    existing_rep = user.reputation if user.reputation else {}
    blended = blend_reputation(existing_rep, new_rep)

    update_user_reputation(db, user_id, blended.to_result())
    return blended


def recalculate_all_reputations(db: Session) -> int:
    """Recalculate reputation for every user in the system.

    Returns the number of users whose reputation was (re)computed.
    """
    users = list_users(db)
    for u in users:
        recompute_author_reputation(db, u.id, user=u)
    return len(users)
