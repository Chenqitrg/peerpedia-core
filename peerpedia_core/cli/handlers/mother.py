# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Mother — friendly user guide for academics who don't live in the terminal."""

from __future__ import annotations

from rich.panel import Panel

from peerpedia_core.cli.display import console


def _cmd_mother(_args):
    """Show the PeerPedia user guide."""
    console.print(Panel("""
[bold info]Welcome to PeerPedia![/]  I'm [accent]Mother[/], your guide.

PeerPedia is a tool for writing, reviewing, and publishing academic papers
— right from your terminal.  Think of it as a journal that runs on your
own computer, where every paper lives in its own version-controlled history.

[bold]What you can do with PeerPedia[/]

  • Write papers in Markdown (plain text with simple formatting)
  • Submit your work for peer review by colleagues
  • ReviewMetaStorage other people's papers and discuss them
  • Publish finished papers so others can find and cite them
  • Collaborate with co-authors and track every change
  • Sync your work with remote servers to share with the world

[bold]How commands work[/]

  PeerPedia commands look like this:

    peerpedia [what] [action] [options]

  For example:
    [accent]peerpedia article create --title "My Paper"[/]
    │          │       │        │
    │          │       │        └── options (extra details, start with --)
    │          │       └── action (what to do)
    │          └── what (article, review, account, …)
    └── the program name

  You don't need to memorize everything.  Add [muted]--help[/] to any command
  to see what it does and get examples you can copy.

[bold]Your first paper — a step-by-step walkthrough[/]

  [bold]Step 1: Create your identity[/]
    [accent]peerpedia account register --name "Marie Curie"[/]
    This makes you a user.  Your name is how others will find you.
    You'll be asked to set a password — keep it safe, there is no reset.

  [bold]Step 2: Write a paper[/]
    [accent]peerpedia article create --title "Research on Radioactivity"[/]
    This opens your text editor.  Write your paper in Markdown format
    (just type normally — use # for headings, * for italics, like you
    would in any plain-text note).  Save and close the editor when done.

    If you prefer to type inline:
    [accent]peerpedia article create --title "Research on Radioactivity" \\[/]
    [accent]    --content "# Abstract\\n\\nThis paper investigates..."[/]

  [bold]Step 3: See what you've written[/]
    [accent]peerpedia article list --mine[/]
    Shows all your papers.  Each one gets a short ID like "abc12345".
    Use that ID to refer to the paper in other commands.

    [accent]peerpedia article show abc12345[/]
    See the paper's details (title, status, scores).

    [accent]peerpedia article show abc12345 --show full[/]
    Read the full text.

  [bold]Step 4: Revise your draft[/]
    [accent]peerpedia article edit abc12345[/]
    Opens your editor again.  Make changes, save, and a new version
    is recorded.  PeerPedia keeps every version — you can always go back.

    [accent]peerpedia article diff abc12345 ~1 HEAD[/]
    See what changed between the last version (~1) and the current one (HEAD).
    Think of this as "track changes" for your paper.

  [bold]Step 5: Submit for peer review[/]
    [accent]peerpedia article publish abc12345 \\[/]
    [accent]    --scores "orig=4,rigor=3,comp=4,ped=3,imp=5"[/]

    This submits your paper to the "sedimentation pool" — a 3-day public
    review period.  You also give your paper a self-assessment on five
    dimensions (each scored 1–5):

      orig  = originality    — how novel is your idea?
      rigor = rigor          — how sound is your method?
      comp  = completeness   — how thorough is your work?
      ped   = pedagogy       — how clearly is it written?
      imp   = impact         — how much potential influence?

    After 3 days (if no issues are raised), the paper auto-publishes.
    You can speed this up with:  [accent]peerpedia article scan[/]

  [bold]Step 6: Get reviewed by colleagues[/]
    Ask someone to review your paper:
    [accent]peerpedia review invite abc12345 --user @pierre[/]

    They'll receive a notification and can submit a review:
    [accent]peerpedia review submit abc12345 \\[/]
    [accent]    --scores "orig=4,rigor=3,comp=4,ped=4,imp=4" \\[/]
    [accent]    --comment "A thorough treatment of the subject..."[/]

    See all reviews:
    [accent]peerpedia review list abc12345[/]

    Reply to a reviewer's comments:
    [accent]peerpedia review reply abc12345 --to @pierre[/]

  [bold]Step 7: Discover other people's work[/]
    [accent]peerpedia article list[/]
    All public papers.

    [accent]peerpedia article list --search "radioactivity"[/]
    Papers with "radioactivity" in the title.

    [accent]peerpedia article list --feed[/]
    Papers from people you follow (your personal reading list).

    [accent]peerpedia follow @einstein[/]
    Add someone to your feed.  Their new papers will appear in --feed.

    [accent]peerpedia bookmark add abc12345[/]
    Save a paper to read later.  Find it with --bookmarked.

[bold]Working with co-authors[/]

    [accent]peerpedia maintainer add abc12345 --target-user @marie[/]
    Add Marie as a co-author.  She can now edit and publish the paper.

    [accent]peerpedia maintainer consent abc12345[/]
    When there are multiple authors, everyone must consent before
    publishing.  This command records your approval.

    [accent]peerpedia maintainer list abc12345[/]
    See all co-authors of a paper.

[bold]Forking and merging (like branching a paper)[/]

    If you want to build on someone else's published paper:
    [accent]peerpedia fork abc12345[/]
    Creates your own copy that you can edit independently.

    After making improvements, propose merging back:
    [accent]peerpedia merge propose def67890 --target abc12345[/]

    The original author can accept your changes:
    [accent]peerpedia merge accept proposal-1 --target abc12345[/]

[bold]Syncing with a peer server[/]

    If your research group runs a PeerPedia server, you can sync:
    [accent]peerpedia sync status --server https://peer.example.com[/]
    Check if you're connected.

    [accent]peerpedia sync push --server https://peer.example.com[/]
    Send your papers and reviews to the server.

    [accent]peerpedia sync pull --server https://peer.example.com[/]
    Download new papers and reviews from the server.

    Syncing is optional — everything works offline by default.

[bold]Useful shortcuts[/]

    • Reference papers by any part of their title:
      [accent]peerpedia article show "electrodynamics"[/]
      (No need to memorize IDs — PeerPedia finds the match.)

    • Reference people by @name:
      [accent]peerpedia follow @einstein[/]
      (The @ sign tells PeerPedia you mean a person, not a paper.)

    • BookmarkStorage important papers:
      [accent]peerpedia bookmark add abc12345[/]
      [accent]peerpedia article list --bookmarked[/]

    • See your notifications:
      [accent]peerpedia notifications[/]
      (Review invitations, replies, new followers — all appear here.)

    • Open the interactive REPL (no need to type "peerpedia" every time):
      Just type [accent]peerpedia[/] with no arguments.

    • Get examples for any command:
      [accent]peerpedia article create --help[/]

[bold]Concepts you might wonder about[/]

    [bold]What is a "UUID"?[/]
    Every paper and user gets a unique ID like "abc12345-6789-...".
    You only need the first few characters (like "abc12345") to refer to it.
    You can also use title keywords or @names instead of IDs.

    [bold]What are ~1 and HEAD?[/]
    These refer to versions of your paper.  HEAD = the latest version.
    ~1 = one version ago.  ~3 = three versions ago.  Think of it like
    "undo history" — every edit is saved, and you can compare any two.

    [bold]What is "sedimentation"?[/]
    When you publish a paper, it enters a 3-day review period.  During
    this time, peers can submit reviews.  If no major issues are found,
    the paper automatically becomes "published" after 3 days.  This
    prevents spam and ensures every paper gets a chance to be reviewed.

    [bold]What about privacy?[/]
    Draft papers are private — only you and your co-authors can see them.
    Published papers are public — anyone can read and cite them.
    Everything is stored on your computer.  The peer server is optional.

[muted]Need more help?  Run 'peerpedia --help' for the full command list,
or 'peerpedia <command> --help' for detailed options and examples.[/]
""", title="Mother — PeerPedia Guide", border_style="accent", title_align="left"))
