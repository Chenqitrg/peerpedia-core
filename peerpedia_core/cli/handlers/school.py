# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""School command — top users ranked by follower count."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _resolve_server_url
from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.social as _social


@with_context
def _cmd_school(ctx, args):
    """List top users ranked by follower count — the user directory."""
    limit = getattr(args, "limit", 20) or 20
    local = getattr(args, "local", False)
    server = _resolve_server_url(args) if not local else ""
    return _social.school(ctx, limit=limit, local=local, server=server)
