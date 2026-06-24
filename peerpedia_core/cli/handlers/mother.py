# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""?Mother — interactive user guide.

TODO(mother-agent): Mother evolves through four phases:

  Phase 1 — Knowledge Crawler
    Traverse the P2P network along three graph axes: social (follow→peer
    →articles), citation (cite→cited→cited-by transitive closure), and
    tag (tag→subfield_of→related_to→articles).  Build a local index of
    articles, authors, reviews, and their relationships.

  Phase 2 — Structure Recognition
    Identify article outlines, argument structures, and inter-article
    relationships (contradicts, extends, replicates, supersedes).  Build
    a knowledge map of the peer network — not just "what exists" but
    "how things connect."

  Phase 3 — Writing Assistant
    User writes an article section → Mother suggests additions, flags
    missing citations, highlights related work from the crawled corpus.
    Mother's suggestions are grounded in the actual peer-reviewed
    literature on the network, not generic model knowledge.

  Phase 4 — Autonomous Agent
    Mother writes, polishes, and reviews articles independently.  She
    is the peer who has read everything — her intelligence comes from
    the P2P graph, not from model weights alone.  She can be a reviewer,
    a co-author, or a reader who surfaces connections no human noticed.

  CLI integration: ``peerpedia mother ask "..."`` sends queries to the
  agent.  The REPL can invoke Mother inline (``:mother "..."``).  Mother
  uses the user's own API key from ``~/.peerpedia/config.json`` — no
  central billing, no server-side costs.
"""

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

[bold]Identity & signing[/]
  [accent]account login --name <name>[/]
      Log in to load your signing key for this session.
      PeerPedia signs every commit you make with your private key.
      Remote peers verify signatures — unsigned commits are rejected.

  [bold yellow]⚠  Do NOT use raw git commands to commit.[/]
      Commits made with [muted]git commit[/] instead of [accent]peerpedia article edit[/]
      or [accent]review submit[/] will have no Pubkey trailer and no signature.
      They will not be tracked in the local database, and remote peers
      will reject them during [accent]sync[/].

  [accent]account whoami[/]            Show your current session identity

[bold]Tips[/]
  • Use [muted]--json[/] on any command for machine-readable output.
  • Type [muted]peerpedia[/] with no arguments to enter the REPL.
  • Run [muted]peerpedia <command> --help[/] to see all options for a command.

[muted]In the future, I'll be able to answer questions and help you write.
For now, this guide is all I can offer.[/]
""", title="?Mother — PeerPedia Guide", border_style="accent", title_align="left"))
