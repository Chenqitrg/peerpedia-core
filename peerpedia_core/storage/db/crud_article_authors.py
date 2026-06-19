# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git-derived author resolution and rebuild logic.

These functions bridge git commit history and the article_authors join table.
They are separate from ``crud_article`` because they depend on the git backend,
not just the database.
"""

from __future__ import annotations

import git
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.crud_article import add_article_authors, get_author_ids
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR


# ── Git email → user resolution ─────────────────────────────────────────


def resolve_user_id_from_git_email(session: Session, email: str) -> str:
    """Resolve a user ID from a git commit email.

    Only accepts ``{UUID}@peerpedia`` format (User.id lookup).
    Raises ValueError if the email does not resolve to a known user.
    """
    local = email.split("@", 1)[0].strip()
    u = session.get(User, local)
    if u is None:
        raise ValueError(f"No user found for git email: {email}")
    return u.id


def get_authors_from_git(
    repo_path,
    session: Session,
    since_hash: str | None = None,
) -> set[str]:
    """Extract unique author user IDs from git commit log.

    Scans commits reachable from HEAD. Uses git range notation
    ``since..HEAD`` for incremental scans — handles merge DAGs
    correctly without missing author chains.

    Returns only authors found in git commits — the caller is
    responsible for merging with existing DB authors via set union.
    """
    repo = git.Repo(repo_path)

    user_ids: set[str] = set()

    if since_hash:
        commits = repo.iter_commits(rev=f"{since_hash}..HEAD")
    else:
        commits = repo.iter_commits()

    for commit in commits:
        user_id = resolve_user_id_from_git_email(session, commit.author.email)
        user_ids.add(user_id)

    return user_ids


# ── Rebuild & validate ──────────────────────────────────────────────────


def rebuild_article_authors(
    session: Session,
    article_id: str,
    new_author_ids: set[str],
) -> None:
    """Append new authors to article_authors (never delete existing ones).

    Updates ``article.last_author_rebuild_hash`` to current repo HEAD.
    """
    existing = set(get_author_ids(session, article_id))
    merged = existing | new_author_ids

    if merged != existing:
        session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()
        add_article_authors(session, article_id, list(merged))

    article = session.get(Article, article_id)
    rp = DEFAULT_ARTICLES_DIR / article_id
    repo = git.Repo(rp)
    article.last_author_rebuild_hash = repo.head.commit.hexsha
    session.commit()




