# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Mother — friendly user guide and walkthrough."""

from __future__ import annotations

from pathlib import Path
from peerpedia_core.cli.info import console, _page

_HELP_DIR = Path(__file__).resolve().parent.parent / "help"


def _cmd_mother(_args):
    """Display the PeerPedia user guide — a complete walkthrough."""
    mother_path = _HELP_DIR / "mother.txt"
    if mother_path.is_file():
        content = mother_path.read_text()
        _page(content)
    else:
        console.print("[bold]Welcome to PeerPedia![/]")
        console.print()
        console.print("Try [accent]peerpedia --help[/] for the full command list.")
        console.print("Or [accent]peerpedia <command> --help[/] for detailed examples.")
