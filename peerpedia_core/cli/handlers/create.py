# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Create an article."""

from __future__ import annotations

from peerpedia_core.cli.handler import with_context
from peerpedia_core.cli.handlers.edit import _get_article_content
import peerpedia_core.app.commands.article as _article


@with_context
def _cmd_article_create(ctx, args):
    """Create a new article."""
    return _article.create(
        ctx, title=args.title,
        format=getattr(args, "format", "markdown"),
        content=_get_article_content(args),
        publish=getattr(args, "publish", False),
        scores_str=getattr(args, "scores", None),
    )
