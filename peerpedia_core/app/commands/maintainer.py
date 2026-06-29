# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Maintainer commands — manage article co-authors."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.refs import require_article, require_user, require_user_by_ref
from peerpedia_core.app.result import AppResult
from peerpedia_core.core import (
    add_maintainer_to_article, consent_to_publish,
    list_maintainers, remove_maintainer_from_article, revoke_publish_consent,
)
from peerpedia_core.types import short_id


def add(ctx: AppContext, *, article_ref: str, target_ref: str) -> AppResult:
    """Add a user as a co-author (maintainer) of an article."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    target = require_user_by_ref(ctx.db, target_ref)
    # ── Execute ──
    add_maintainer_to_article(ctx.db, article.id, user_id, target.id)
    ctx.db.commit()
    return AppResult("OK", params={"msg": f"Added {target.name} as maintainer"})


def remove(ctx: AppContext, *, article_ref: str, target_ref: str) -> AppResult:
    """Remove a user from maintainers."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    target = require_user_by_ref(ctx.db, target_ref)
    # ── Execute ──
    remove_maintainer_from_article(ctx.db, article.id, user_id, target.id)
    ctx.db.commit()
    return AppResult("OK", params={"msg": f"Removed {target.name} from maintainers"})


def list_article_maintainers(ctx: AppContext, *, article_ref: str) -> AppResult:
    """List all maintainers of an article."""
    # ── Resolve ──
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    maintainers = list_maintainers(ctx.db, article.id)
    return AppResult("", data={"maintainers": maintainers})


def consent(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Consent to publish or merge as a maintainer."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    consent_to_publish(ctx.db, article.id, user_id)
    ctx.db.commit()
    return AppResult("OK", params={"msg": "Consent recorded"})


def revoke(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Revoke publish/merge consent."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    revoke_publish_consent(ctx.db, article.id, user_id)
    ctx.db.commit()
    return AppResult("OK", params={"msg": "Consent revoked"})
