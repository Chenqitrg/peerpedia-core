# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Schema command — JSON Schema for AI tool discovery."""

from __future__ import annotations

from peerpedia_core.app.commandspec.schema import build as _build_schema


def _cmd_schema(args):
    """Output the full command schema as JSON (for AI tool discovery)."""
    target = getattr(args, "command", None)
    print(_build_schema(target=target))
