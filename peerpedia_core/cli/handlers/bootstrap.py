# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bootstrap — load a user stub on a new device for key recovery."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.account as _account


@with_context
def _cmd_bootstrap(ctx, args):
    """Create a minimal user stub on a new device for key recovery."""
    return _account.bootstrap(ctx, from_json=args.from_,
        peer=getattr(args, "peer", None))
