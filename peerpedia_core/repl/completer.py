# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL tab completion — command names, flags, article IDs, @usernames."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

import peerpedia_core.repl.state as _st
from peerpedia_core.app.commandspec import COMMAND_GROUPS, TOP_LEVEL_COMMANDS
from peerpedia_core.repl.dispatch import _META_COMMANDS

LAST_TOKEN_RE = re.compile(r"\S+$")
EXTRA_REPL_FLAGS = ("--json", "--rich")


def _flag_name(raw_name: str) -> str:
    """Convert a CommandSpec arg name to a CLI-style flag name."""
    return f"--{raw_name.replace('_', '-')}"


def _iter_command_args():
    """Yield all arguments from grouped and top-level CommandSpec commands."""
    for group in COMMAND_GROUPS:
        for command in group.commands:
            yield from command.args
    for command in TOP_LEVEL_COMMANDS:
        yield from command.args


def build_flags() -> list[str]:
    """Generate all flag names from CommandSpec plus REPL-only flags."""
    flags = {
        _flag_name(arg.name)
        for arg in _iter_command_args()
        if not arg.positional
    }
    flags.update(EXTRA_REPL_FLAGS)
    return sorted(flags)


FLAGS = build_flags()


def build_command_list() -> list[str]:
    """Build all known command strings: groups, actions, top-level, and meta commands."""
    commands: set[str] = set()
    for group in COMMAND_GROUPS:
        commands.add(group.name)
        for command in group.commands:
            if command.action:
                commands.add(f"{group.name} {command.action}")
    for command in TOP_LEVEL_COMMANDS:
        commands.add(command.cmd_id)

    result = sorted(commands)
    for mc in _META_COMMANDS:
        if mc not in commands:
            result.append(mc)
    return result


def _last_token(text: str) -> str | None:
    """Return the non-space token immediately before the cursor."""
    match = LAST_TOKEN_RE.search(text)
    return match.group(0) if match else None


def _dynamic_completion_words() -> set[str]:
    """Return dynamic REPL completion words: article IDs and @usernames."""
    return set(_st.session.completion_words)


def _matching_completions(
    words: Iterable[str],
    prefix: str,
    *,
    start_position: int,
    yielded: set[str],
) -> Iterator[Completion]:
    """Yield completions whose text starts with *prefix*, skipping duplicates."""
    prefix_lower = prefix.lower()
    for word in sorted(words, key=str.lower):
        if word in yielded:
            continue
        if word.lower().startswith(prefix_lower):
            yielded.add(word)
            yield Completion(word, start_position=start_position, display=word)


class ReplCompleter(Completer):
    """Completer for REPL commands, flags, article IDs, and @usernames."""

    def __init__(self, static_words: Iterable[str]) -> None:
        self._static_words = frozenset(static_words)

    def _complete_prefix(self, prefix: str,
                         words: set[str], yielded: set[str]) -> Iterator[Completion]:
        """Try multi-word prefix match — e.g. 'article p' → 'article publish'."""
        if prefix:
            yield from _matching_completions(
                words, prefix, start_position=-len(prefix), yielded=yielded,
            )

    def _complete_token(self, text: str,
                        words: set[str], yielded: set[str]) -> Iterator[Completion]:
        """Try last-token match — e.g. 'review @al' → '@alice'."""
        token = _last_token(text)
        if token:
            yield from _matching_completions(
                words, token, start_position=-len(token), yielded=yielded,
            )

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterator[Completion]:
        text = document.text_before_cursor
        if not text:
            return
        words = self._all_words()
        yielded: set[str] = set()
        yield from self._complete_prefix(text.lstrip(), words, yielded)
        yield from self._complete_token(text, words, yielded)

    def _all_words(self) -> set[str]:
        return set(self._static_words) | _dynamic_completion_words()


def make_completer(static_words: frozenset[str]) -> Completer:
    """Build a REPL completer."""
    return ReplCompleter(static_words)
