# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review commands — submit and list."""

from __future__ import annotations

from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _parse_scores, _page, _ok, _die, _json_out,
    DEFAULT_ARTICLES_DIR,
)
from peerpedia_core.cli.display import _stars, console
from peerpedia_core.cli.sync_utils import _try_sync
from peerpedia_core.commands import submit_review, get_reviews_for_article, get_user


@_with_db
def _cmd_review_submit(db, args):
    """Submit a review with 5-dim scores + optional comment.

    args: article_id [positional], --scores, --comment, --user, --json
    """
    scores = _parse_scores(args.scores)
    result = submit_review(
        db, article_id=args.article_id, reviewer_id=_resolve_user(db, args.user),
        scores=scores,
        comment=args.comment or "",
    )
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok("Review submitted")
        console.print(_stars(scores))


@_with_db
def _cmd_review_list(db, args):
    """List all reviews for an article.

    args: article_id [positional], --show [meta|full], --user, --json
    """
    reviews = get_reviews_for_article(db, args.article_id)
    if args.json:
        _json_out([{"id": r.id, "reviewer_id": r.reviewer_id, "scores": r.scores} for r in reviews])
        return
    if not reviews:
        console.print("[muted]No reviews yet.[/]")
        return

    show_mode = getattr(args, "show", "meta")

    for r in reviews:
        ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "unknown"
        reviewer = get_user(db, r.reviewer_id)
        label = reviewer.name if reviewer else r.reviewer_id[:8]
        console.print(f"[bold]{label}[/]  [muted]{ts}[/]  {_stars(r.scores)}")
        console.print()

    if show_mode == "full":
        rp = DEFAULT_ARTICLES_DIR / args.article_id
        reviews_dir = rp / "reviews"
        if not reviews_dir.is_dir():
            _die(f"DB has reviews but no reviews/ directory on disk for article {args.article_id}")

        parts: list[str] = []
        for reviewer_dir in sorted(reviews_dir.iterdir()):
            threads_dir = reviewer_dir / "threads"
            for tf in sorted(threads_dir.glob("*.md")):
                parts.append(tf.read_text())
                parts.append("")
        if parts:
            _page("\n".join(parts))
        else:
            console.print("[muted]No review threads found.[/]")
