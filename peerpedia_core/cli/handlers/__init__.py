# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""CLI handlers — facade for ``parser.py``.

All handler imports go through here.  ``parser.py`` must NOT import from
individual handler files directly.  Handlers themselves must NOT import
from ``storage/`` — they call ``commands/`` for all data access.
"""

from peerpedia_core.cli.handlers.account import _cmd_account_search, _cmd_login, _cmd_register, _cmd_whoami
from peerpedia_core.cli.handlers.articles import (
    _cmd_article_create,
    _cmd_article_delete,
    _cmd_article_edit,
    _cmd_article_list,
    _cmd_article_publish,
    _cmd_article_scan,
    _cmd_article_search,
    _cmd_article_show,
)
from peerpedia_core.cli.handlers.compile_ import _cmd_compile
from peerpedia_core.cli.handlers.maintainers import (
    _cmd_maintainer_add,
    _cmd_maintainer_list,
    _cmd_maintainer_remove,
)
from peerpedia_core.cli.handlers.mother import _cmd_mother
from peerpedia_core.cli.handlers.reviews import _cmd_review_list, _cmd_review_submit
from peerpedia_core.cli.handlers.social import (
    _cmd_bookmark_add,
    _cmd_bookmark_remove,
    _cmd_follow_user,
    _cmd_fork,
    _cmd_merge_accept,
    _cmd_merge_propose,
    _cmd_unfollow_user,
)
from peerpedia_core.cli.handlers.sync import _cmd_sync_push, _cmd_sync_status
