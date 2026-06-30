# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Argument parser — declarative command definitions, single builder loop."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from peerpedia_core.app.commandspec import (
    COMMAND_GROUPS, TOP_LEVEL_COMMANDS, _UNSET,
    ArgSpec as SharedArgSpec,
    CommandSpec as SharedCommandSpec, CommandGroupSpec as SharedCommandGroupSpec,
)
from peerpedia_core.cli.dispatch import dispatch
from peerpedia_core.types.scores import SCORE_FORMAT_EXAMPLE, _SCORE_DIMS_LIST

_HELP_DIR = Path(__file__).resolve().parent / "help"


def _load_help(name: str) -> str:
    path = _HELP_DIR / f"{name}.txt"
    return path.read_text() if path.is_file() else ""


def _shared_arg_to_cli(arg: SharedArgSpec) -> ArgSpec:
    """Convert a shared ``ArgSpec`` to CLI's argparse-oriented ``ArgSpec``."""
    name = arg.name
    if arg.positional:
        args: tuple[str, ...] = (name,)
    elif not arg.takes_value:
        args = (f"--{name.replace('_', '-')}",)
    else:
        args = (f"--{name.replace('_', '-')}",)

    kwargs: dict = {}
    if arg.help:
        kwargs["help"] = arg.help
    if arg.required:
        kwargs["required"] = True
    if arg.type is not None:
        kwargs["type"] = arg.type
    if arg.choices:
        kwargs["choices"] = arg.choices
    if arg.metavar:
        kwargs["metavar"] = arg.metavar
    if arg.default is not _UNSET:
        kwargs["default"] = arg.default
    if not arg.takes_value and not arg.positional:
        kwargs["action"] = "store_true"
    # Special case: --from → dest="from_" (Python keyword avoidance)
    if name == "from_" and not arg.positional:
        kwargs["dest"] = "from_"

    return ArgSpec(args=args, kwargs=kwargs)


def _shared_cmd_to_cli(cs: SharedCommandSpec) -> Command:
    """Convert a shared ``CommandSpec`` to CLI's ``Command``."""
    if cs.action is not None:
        name = cs.action
    elif cs.group:
        name = ""  # lives directly on group parser
    else:
        name = cs.cmd_id  # top-level command
    return Command(
        name=name,
        cmd_id=cs.cmd_id,
        args=[_shared_arg_to_cli(a) for a in cs.args],
        help_file=cs.help_file,
    )


def _build_commands() -> list[CommandGroup | Command]:
    """Build CLI's ``COMMANDS`` list from the shared command specs."""
    result: list[CommandGroup | Command] = []

    for gs in COMMAND_GROUPS:
        result.append(CommandGroup(
            name=gs.name,
            help=gs.help,
            commands=[_shared_cmd_to_cli(c) for c in gs.commands],
        ))

    for cs in TOP_LEVEL_COMMANDS:
        result.append(_shared_cmd_to_cli(cs))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Command definition types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ArgSpec:
    args: tuple[str, ...]
    kwargs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    name: str           # CLI subcommand name ("" = commands live directly on the group parser)
    cmd_id: str         # dispatch command_id
    args: list[ArgSpec] = field(default_factory=list)
    help_file: str = ""  # extended help file name, loaded on access

    @property
    def help_epilog(self) -> str:
        """Extended help text loaded from ``cli/help/<help_file>.txt``."""
        return _load_help(self.help_file) if self.help_file else ""


@dataclass(frozen=True)
class CommandGroup:
    name: str
    help: str
    commands: list[Command]


# ═══════════════════════════════════════════════════════════════════════════════
# Command definitions
# ═══════════════════════════════════════════════════════════════════════════════

COMMANDS: list[CommandGroup | Command] = _build_commands()


# ═══════════════════════════════════════════════════════════════════════════════
# Help epilog
# ═══════════════════════════════════════════════════════════════════════════════

_SECTIONS = [
    ("Writing & publishing",                     ["article"]),
    ("Peer review",                              ["review"]),
    ("Collaboration (fork, merge, co-authors)",  ["merge", "fork", "maintainer"]),
    ("Social & discovery",                       ["follow", "unfollow", "following",
                                                  "followers", "school", "bookmark",
                                                  "share", "alias"]),
    ("Sync & networking",                        ["sync", "server"]),
    ("Account & utilities",                      ["account", "notifications",
                                                  "compile", "schema", "help", "mother"]),
]

_NAME_WIDTH = 14  # help output column alignment


_EXAMPLES = """\
EXAMPLES — real tasks you can copy and paste

  Your first paper:
    peerpedia account register --name "Albert Einstein"
    peerpedia article create --title "On the Electrodynamics of Moving Bodies"
    peerpedia article publish abc12345 --scores "orig=5,rigor=4,comp=4,ped=3,imp=5"

  Finding papers to read:
    peerpedia article list                          # all public papers
    peerpedia article list --search "quantum"       # papers about quantum topics
    peerpedia article list --feed                    # papers from people you follow
    peerpedia article show abc12345                  # read a paper's details
    peerpedia article show abc12345 --show full      # read the full text

  Improving your draft:
    peerpedia article edit abc12345                  # open editor to revise
    peerpedia article diff abc12345 ~1 HEAD          # see what changed last time

  Peer reviewing:
    peerpedia review submit abc12345 \\
        --scores "orig=4,rigor=3,comp=4,ped=3,imp=5" \\
        --comment "This paper presents a novel approach to..."
    peerpedia review list abc12345                   # see all reviews of a paper

  Working with others:
    peerpedia account search Einstein                # find a colleague
    peerpedia follow @einstein                       # follow their work
    peerpedia maintainer add abc12345 --target-user @bob  # add a co-author
    peerpedia fork abc12345                          # create your own copy to revise

  Sharing with peers:
    peerpedia sync push --server https://peer.example.com
    peerpedia sync pull --server https://peer.example.com

Add --help to any command for detailed options and more examples:
    peerpedia article create --help
    peerpedia review submit --help

New to the command line?  Run:  peerpedia mother"""


def _build_epilog() -> str:
    """Build the grouped command list for --help output."""
    # ── Index: name → Command | CommandGroup ──────────────────────────
    index: dict[str, Command | CommandGroup] = {}
    for item in COMMANDS:
        index[item.name] = item
        if isinstance(item, CommandGroup):
            for cmd in item.commands:
                if cmd.name:
                    index[cmd.name] = cmd

    # ── Render ────────────────────────────────────────────────────────
    lines: list[str] = []
    for section, names in _SECTIONS:
        lines.append(f"  {section}")
        for n in names:
            item = index.get(n)
            if item is None:
                continue
            if isinstance(item, CommandGroup):
                subs = [c.name for c in item.commands if c.name]
                lines.append(f"    {item.name:<{_NAME_WIDTH}} {', '.join(subs)}")
            else:
                lines.append(f"    {item.name:<{_NAME_WIDTH}} {item.name}")
        lines.append("")
    return "\nCOMMANDS\n" + "\n".join(lines) + "\n" + _EXAMPLES


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════

_COMMON_ARGS = [
    (("--json",), {"action": "store_true", "help": "Output as JSON"}),
    (("--rich",), {"action": "store_true", "help": "Output as human-readable Rich text"}),
]


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser from the COMMANDS table."""
    import importlib.metadata
    try:
        _version = importlib.metadata.version("peerpedia-core")
    except importlib.metadata.PackageNotFoundError:
        _version = "unknown"

    parser = argparse.ArgumentParser(
        "peerpedia",
        description="PeerPedia — peer review from the terminal",
        epilog=_build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version}")
    subs = parser.add_subparsers(dest="command")

    for item in COMMANDS:
        if isinstance(item, CommandGroup):
            grp = subs.add_parser(item.name, help=item.help)
            sub = grp.add_subparsers(dest="subcommand")
            for cmd in item.commands:
                _register(_target_parser(grp, sub, cmd), cmd)
        else:
            _register(_target_parser(subs, subs, item), item)

    return parser


def _target_parser(group_parser, subparsers, cmd: Command) -> argparse.ArgumentParser:
    """Return the parser to register *cmd* on — group or subparser."""
    if cmd.name == "":
        return group_parser
    return subparsers.add_parser(
        cmd.name, help=cmd.name,
        epilog=cmd.help_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _register(p: argparse.ArgumentParser, cmd: Command) -> None:
    """Add args, common args, and dispatch to a parser."""
    for spec in cmd.args:
        p.add_argument(*spec.args, **spec.kwargs)
    for args, kwargs in _COMMON_ARGS:
        p.add_argument(*args, **kwargs)
    p.set_defaults(command_id=cmd.cmd_id, func=dispatch)


