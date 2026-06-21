# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""?Mother — interactive user guide."""

from __future__ import annotations

from rich.panel import Panel

from peerpedia_core.cli.display import console


def _cmd_mother(_args):
    """Show the PeerPedia user guide."""
    console.print(Panel("""
[bold info]Welcome to PeerPedia![/]  I'm [accent]Mother[/], your guide.

PeerPedia is a peer-to-peer platform for academic writing, reviewing, and
publishing.  Every article lives in its own git repository on your machine.

[bold]Getting started[/]
  [accent]peerpedia account register --name <your-name>[/]
      Create your identity.  You'll use this name for all actions.

  [accent]peerpedia article create --title "My Paper"[/]
      Write your first article.  An editor will open for you to type content.
      Pass [muted]--content "..."[/] to skip the editor.

[bold]Core workflow[/]
  [accent]article show <id>[/]       Read an article and its reviews
  [accent]article edit <id>[/]        Revise your draft
  [accent]article publish <id>[/]     Submit to the sedimentation pool
  [accent]review submit <id>[/]       Peer-review someone else's article
  [accent]article list[/]             Browse all local articles

[bold]Collaboration[/]
  [accent]fork <id>[/]                Copy a published article to start your version
  [accent]merge propose <fork> --target <original>[/]
      Propose merging your changes back
  [accent]bookmark add <id>[/]        Save an article for later

[bold]Peer-to-peer sync[/]
  [accent]sync status[/]              Check connection to a peer
  [accent]sync push[/]                Send your changes to a peer server

[bold]Tips[/]
  • Use [muted]--json[/] on any command for machine-readable output.
  • Use [muted]--user @name[/] to act as a specific user.
  • Type [muted]peerpedia[/] with no arguments to enter the REPL.
  • Run [muted]peerpedia <command> --help[/] to see all options for a command.

[muted]In the future, I'll be able to answer questions and help you write.
For now, this guide is all I can offer.[/]
""", title="?Mother — PeerPedia Guide", border_style="accent", title_align="left"))
