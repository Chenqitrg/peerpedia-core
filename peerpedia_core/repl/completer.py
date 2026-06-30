# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL tab completion — command names, flags, article IDs, @usernames."""

from __future__ import annotations

import re

from prompt_toolkit.completion import Completer, Completion

import peerpedia_core.repl.state as _st
from peerpedia_core.app.commandspec import COMMAND_GROUPS, TOP_LEVEL_COMMANDS
from peerpedia_core.repl.dispatch import _META_COMMANDS


def build_flags() -> list[str]:
    """Generate all flag names from shared CommandSpec (always in sync)."""
    flags: set[str] = set()
    for grp in COMMAND_GROUPS:
        for cmd in grp.commands:
            for arg in cmd.args:
                if not arg.positional:
                    flags.add(f"--{arg.name.replace('_', '-')}")
    for cmd in TOP_LEVEL_COMMANDS:
        for arg in cmd.args:
            if not arg.positional:
                flags.add(f"--{arg.name.replace('_', '-')}")
    flags.update(["--json", "--rich"])  # CLI-only, useful in REPL completion
    return sorted(flags)


FLAGS = build_flags()


def build_command_list() -> list[str]:
    """Build the list of all known command strings (groups, actions, top-level)."""
    commands: list[str] = []
    for grp in COMMAND_GROUPS:
        commands.append(grp.name)
        for cmd in grp.commands:
            if cmd.action:
                commands.append(f"{grp.name} {cmd.action}")
    for cmd in TOP_LEVEL_COMMANDS:
        if cmd.cmd_id not in commands:
            commands.append(cmd.cmd_id)
    return sorted(set(commands)) + _META_COMMANDS


def make_completer(static_words: frozenset[str]) -> Completer:
    """Build a ``_ReplCompleter`` that matches the last word of input."""

    class _ReplCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text:
                return
            m = re.search(r'(\S+)$', text)
            if not m:
                return
            word_before = m.group(1)
            low = word_before.lower()

            all_words: set[str] = set(static_words) | set(_st._repl_completion_words)

            yielded: set[str] = set()
            for w in sorted(all_words):
                if w in yielded:
                    continue
                if w.lower().startswith(low):
                    yielded.add(w)
                    yield Completion(w, start_position=-len(word_before), display=w)

    return _ReplCompleter()
