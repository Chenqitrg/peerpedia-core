# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Command specification — single source of truth for all CLI/REPL commands.

``types.py``    — ArgSpec, CommandSpec, CommandGroupSpec data structures
``handlers.py`` — adapter functions (dict → typed app command)
``registry.py`` — COMMAND_GROUPS, TOP_LEVEL_COMMANDS, find_spec(), lookups
"""

from peerpedia_core.app.commandspec.types import (
    ArgSpec, CommandSpec, CommandGroupSpec, _UNSET,
)
from peerpedia_core.app.commandspec.registry import (
    COMMAND_GROUPS, TOP_LEVEL_COMMANDS, find_spec, spec_for_cmd_id,
)
