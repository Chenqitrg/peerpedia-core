# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Sync commands — status, pull, discover."""

from __future__ import annotations

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.cli.bundle_utils import _resolve_server_url
from peerpedia_core.cli.decorators import with_context


@with_context
def _cmd_sync_status(ctx, args):
    """Check connection to a peer server."""
    server = _resolve_server_url(args)
    return spec_for_cmd_id("sync.status").handler(ctx, {"server": server})


@with_context
def _cmd_sync_pull(ctx, args):
    """Pull article updates from a peer server."""
    server = _resolve_server_url(args)
    return spec_for_cmd_id("sync.pull").handler(ctx, {"server": server})


@with_context
def _cmd_sync_discover(ctx, args):
    """Walk the follow graph to discover new users and articles."""
    server = _resolve_server_url(args)
    depth = getattr(args, "depth", 1) or 1
    max_users = getattr(args, "max_users", 100) or 100
    return spec_for_cmd_id("sync.discover").handler(ctx, {
        "server": server, "depth": depth, "max_users": max_users,
    })
