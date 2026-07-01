# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared helpers for article sub-modules."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import set_sink_start
from peerpedia_core.storage.git import commit_status_marker
from peerpedia_core.types.status import ArticleStatus


def reset_sink(db: Session, article_id: str, rp: Path, extra_days: int) -> None:
    """Write status marker to git and reset sink timer."""
    commit_status_marker(rp, ArticleStatus.SEDIMENTATION)
    set_sink_start(db, article_id, extra_days)
