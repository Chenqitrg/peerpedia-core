# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Command specification types — frontend-agnostic metadata for every command.

These types are the vocabulary that ``registry.py``, ``cli/parser.py``, and
``repl/engine.py`` all share.  ``ArgSpec`` describes one argument; a list of
them plus a handler makes a ``CommandSpec``; related commands form a
``CommandGroupSpec``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.result import AppResult

# ═══════════════════════════════════════════════════════════════════════════════
# Sentinel
# ═══════════════════════════════════════════════════════════════════════════════

_UNSET = object()  # sentinel: no default provided (distinct from None)


# ═══════════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArgSpec:
    """A single command argument, frontend-agnostic.

    The canonical name is underscored (``no_editor``), matching Python
    identifier rules.  Each frontend converts to its own syntax:

    - CLI : ``name="no_editor"`` → ``--no-editor``
    - REPL: ``name="no_editor"`` → matched against ``no-editor`` / ``no_editor``
    """
    name: str                    # canonical: "title", "verbose", "no_editor"
    takes_value: bool = True     # True = expects value; False = boolean flag
    type: type | None = None     # type coercion (None = str)
    default: Any = _UNSET        # _UNSET = no default; None is a valid default
    required: bool = False
    help: str = ""
    choices: list | None = None
    positional: bool = False     # True = positional, False = --flag
    metavar: str | None = None   # display name in help


@dataclass
class CommandSpec:
    """A single command with its args, handler, and help metadata."""
    cmd_id: str                                                # "article.create"
    group: str                                                 # "article"
    action: str | None                                         # "create" or None for top-level
    args: list[ArgSpec] = field(default_factory=list)
    help_file: str = ""                                        # help/<name>.txt
    handler: Callable[[AppContext, dict[str, Any]], AppResult] | None = None
    frontend: Literal["all", "cli", "repl"] = "all"             # which frontend this command targets
    effect: Literal["read", "write", "destructive", "external"] = "read"  # operation category for AI safety


@dataclass
class CommandGroupSpec:
    """A group of related commands (e.g. "article", "account")."""
    name: str
    help: str
    commands: list[CommandSpec]
