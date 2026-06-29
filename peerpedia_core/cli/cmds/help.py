# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Meta-help command — explains how to get help about anything."""

from __future__ import annotations

from pathlib import Path

_HELP_DIR = Path(__file__).resolve().parent.parent / "help"


def _cmd_meta_help(args):
    """Show available help systems and how to use them.

    Usage: ``peerpedia help [topic]``

    Without arguments, shows the meta-help overview.
    With a topic, delegates to ``<topic> --help``.
    """
    topic = getattr(args, "topic", None)
    if topic:
        # Delegate to the command's own --help.
        import subprocess
        subprocess.run(["peerpedia", topic, "--help"])
        return

    # Show meta-help overview.
    meta_path = _HELP_DIR / "_meta.txt"
    if meta_path.is_file():
        print(meta_path.read_text())
    else:
        print("Try: peerpedia --help")
