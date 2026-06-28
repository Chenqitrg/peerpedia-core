# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""CLI handlers — facade for ``parser.py``.

All handler imports go through here.  ``parser.py`` must NOT import from
individual handler files directly.  Handlers themselves must NOT import
from ``storage/`` — they call ``commands/`` for all data access.
"""

from peerpedia_core.cli.handlers.account import _cmd_account_delete, _cmd_account_search, _cmd_whoami
from peerpedia_core.cli.handlers.bootstrap import _cmd_bootstrap
from peerpedia_core.cli.handlers.login import _cmd_login, _cmd_recover
from peerpedia_core.cli.handlers.register import _cmd_register
from peerpedia_core.cli.handlers.create import _cmd_article_create
from peerpedia_core.cli.handlers.edit import (
    _cmd_article_delete, _cmd_article_diff, _cmd_article_edit,
    _cmd_article_publish, _cmd_article_scan,
)
from peerpedia_core.cli.handlers.read import _cmd_article_list, _cmd_article_show
from peerpedia_core.cli.handlers.compile_ import _cmd_compile
from peerpedia_core.cli.handlers.maintainers import (
    _cmd_maintainer_add,
    _cmd_maintainer_consent,
    _cmd_maintainer_list,
    _cmd_maintainer_remove,
    _cmd_maintainer_revoke,
)
from peerpedia_core.cli.handlers.mother import _cmd_mother
from peerpedia_core.cli.handlers.reviews import _cmd_review_accept, _cmd_review_decline, _cmd_review_invite, _cmd_review_list, _cmd_review_rate, _cmd_review_reply, _cmd_review_submit
from peerpedia_core.cli.handlers.alias import _cmd_alias_list, _cmd_alias_remove, _cmd_alias_set
from peerpedia_core.cli.handlers.bookmark import _cmd_bookmark_add, _cmd_bookmark_remove
from peerpedia_core.cli.handlers.fork import _cmd_fork, _cmd_merge_accept, _cmd_merge_propose, _cmd_merge_withdraw
from peerpedia_core.cli.handlers.school import _cmd_school
from peerpedia_core.cli.handlers.share import _cmd_share_add, _cmd_share_list, _cmd_share_remove
from peerpedia_core.cli.handlers.social import (
    _cmd_follow_user, _cmd_followers, _cmd_following, _cmd_unfollow_user,
)
from peerpedia_core.cli.handlers.notifications import (
    _cmd_notifications,
    _cmd_notification_read,
)
from peerpedia_core.cli.handlers.help import _cmd_meta_help
from peerpedia_core.cli.handlers.schema import _cmd_schema
from peerpedia_core.cli.handlers.server import _cmd_server_start
from peerpedia_core.cli.handlers.bundle import _cmd_sync_discover, _cmd_sync_pull, _cmd_sync_status
