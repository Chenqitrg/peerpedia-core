# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Commit trailer parsing — Closes: and Acked-by: for review workflow.

Used by sedimentation editing to enforce that edits reference a review thread,
and by the reputation system to credit reviewers when authors act on feedback.
"""

from __future__ import annotations

import re
from pathlib import Path

from peerpedia_core.storage.git import DEFAULT_ARTICLES_DIR


# Closes: review/{reviewer-dir}/thread-{n}
_CLOSES_RE = re.compile(
    r"^Closes:\s*review/([a-zA-Z0-9_-]+)/thread-(\d+)",
    re.MULTILINE | re.IGNORECASE,
)


def parse_closes_trailer(commit_message: str) -> tuple[str, int] | None:
    """Extract (reviewer_dir, thread_num) from a Closes: trailer.

    Returns None if no valid Closes: trailer is found.
    """
    m = _CLOSES_RE.search(commit_message)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def validate_closes_target(article_id: str, reviewer_dir: str, thread_num: int) -> bool:
    """Check that the referenced thread file exists in the article's git repo."""
    thread_path = (
        DEFAULT_ARTICLES_DIR / article_id / "reviews" / reviewer_dir /
        "threads" / f"{thread_num:03d}.md"
    )
    return thread_path.is_file()


def list_review_threads(article_id: str) -> list[str]:
    """List all review thread paths available for Closes: referencing.

    Returns relative paths like ``review/{dir}/thread-{n}`` for display.
    """
    reviews_dir = DEFAULT_ARTICLES_DIR / article_id / "reviews"
    if not reviews_dir.is_dir():
        return []

    threads: list[str] = []
    for rev_dir in sorted(reviews_dir.iterdir()):
        if not rev_dir.is_dir():
            continue
        thread_dir = rev_dir / "threads"
        if not thread_dir.is_dir():
            continue
        for tf in sorted(thread_dir.glob("*.md")):
            threads.append(f"review/{rev_dir.name}/thread-{tf.stem}")
    return threads
