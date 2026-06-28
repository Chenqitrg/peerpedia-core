# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Create an article."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _try_sync
from peerpedia_core.cli.display import console
from peerpedia_core.cli.handlers.edit import _get_article_content
from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _get_session_key,
    _resolve_and_display_article, _parse_scores, _ok, _json_out,
)
from peerpedia_core.core import (
    create_article_with_content, get_article, publish_article,
)
from peerpedia_core.storage.db.guards import require_user
from peerpedia_core.types import short_id


@_with_db
def _cmd_article_create(db, args):
    """Create a new article.

    args: --title, --format [markdown|typst], --content, --no-editor,
          --publish, --scores, --json
    """
    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = require_user(db, user_id)
    content = _get_article_content(args)

    result = create_article_with_content(
        db, title=args.title, content=content, format=args.format,
        author_ids=[user_id],
        signing_key_bytes=key_bytes,
        pubkey_hex=user.public_key,
    )
    if args.publish:
        self_review = _parse_scores(args.scores) if args.scores else None
        result = publish_article(
            db, result["id"], user_id, self_review,
            signing_key_bytes=key_bytes, pubkey_hex=user.public_key,
        )
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        article = get_article(db, result["id"])
        _resolve_and_display_article(db, article, author_ids=[user_id])
        console.print(
            f"[dim]Created [accent]{short_id(result['id'])}[/] \"{result['title']}\" (draft)[/]"
        )
        if not args.publish:
            console.print(
                f"[dim]Next: [accent]peerpedia article publish {short_id(result['id'])}[/] "
                "--scores \"orig=4,rigor=3,comp=4,ped=3,imp=4\"[/]"
            )
