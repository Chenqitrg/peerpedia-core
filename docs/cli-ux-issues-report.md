# CLI UX Issues Report — 2026-06-26

Critical, hands-on review of PeerPedia CLI v0.4.0. All findings are from actual
terminal testing — no code reading (except to trace root causes). No debugging,
no fixes applied.

## 🔴 Critical: Crashes

### 1. `peerpedia schema` — complete crash (`ValueError`)

```
$ peerpedia schema
ValueError: too many values to unpack (expected 3, got 4)
```

Same for `peerpedia schema article_create`. This is the **AI tool-discovery command**
— the one meant for agents and scripts to understand available commands. It's 100%
broken. Traceback points to:

```
peerpedia_core/cli/handlers/schema.py:98: _cmd_schema
    for sub_name, handler, arg_specs in subcommands:
```

The COMMAND_GROUPS entries now have 4 elements (the 4th is `extra` kwargs dict),
but the schema handler still unpacks 3.

**Why this matters:** AI agents can't discover commands. Any downstream tool that
depends on `peerpedia schema` is dead.

### 2. `peerpedia ?Mother` — shell glob prevents invocation

```
$ peerpedia ?Mother
(eval):1: no matches found: ?Mother
```

`?` is a shell glob character (matches any single character). In zsh/bash, this
command literally can't be typed without quoting: `peerpedia '?Mother'` or
`peerpedia \?Mother`. But every pointer in the UI says `peerpedia ?Mother`.

**Why this matters:** The "getting started" guide is inaccessible. The welcome
banner says `peerpedia ?Mother ← full guide`, but the command fails.

### 3. `merge propose` — raw SQL traceback leaks to user

```
$ peerpedia merge propose 8c9cda37 --target P3
sqlite3.IntegrityError: FOREIGN KEY constraint failed
[SQL: INSERT INTO merge_proposals (...) VALUES (...)]
(Background on this error at: https://sqlalche.me/e/20/gkpj)
```

Full Python traceback with SQL statement and parameters. Should be caught and
turned into a user-friendly message like "Cannot merge: article is not a fork of
the target."

## 🟠 Performance: 5-6 second hangs

### Root cause: stale `server_default` file

`~/.peerpedia/server_default` contains `http://127.0.0.1:18770` — a server from a
previous session that is no longer running. Every command that checks server
reachability blocks for **5 seconds** (the health check timeout).

### Measured timings

| Command | Time | Notes |
|---|---|---|
| `account whoami` | 0.42s | Fast — no network check |
| `article list --feed` | 0.39s | Fast — no network check |
| `following --user Alice` | **5.76s** | HTTP timeout to stale server |
| `followers --user Alice` | **6.65s**  | HTTP timeout to stale server |
| `sync status` | **5.63s** | HTTP timeout to stale server |
| `school --server http://...` | **6.44s** | HTTP timeout to stale server |

### Why this happens

1. **5-second health check timeout** (`transport/health.py:28`):
   ```python
   def is_online(server_url: str, timeout: float = 5.0) -> bool:
   ```
   The code even has a self-review comment claiming "5 seconds is fine for a
   health check" — it is not.

2. **`_resolve_server_url()` calls `check_clock_skew()` before every network op**
   (`cli/bundle_utils.py:178`). That's an additional 5-second timeout on top of
   `is_online()`.

3. **No connection result caching** — each command independently times out.

4. **`server_default` persists forever** — there's no expiry, no fallback to
   "offline mode", and no prompt to remove a dead server.

### Commands affected (any that call `_resolve_server_url()` or `is_online()`):

- `sync status / push / pull / discover`
- `following --user`, `followers --user`
- `school` (with --server or default)
- `article list --user` (remote query)
- `account login --peer`

## 🟡 UX Issues

### Confusing output / misleading messages

#### 4. `article scan` says "Published" instead of "Scanned"

```
$ peerpedia article scan
✓ Published 0 article(s)
```

The user ran **scan**, the output says **Published**. The green checkmark
reinforces the wrong message. Should say "Scan complete — 0 articles ready for
publish" or similar.

#### 5. Author displayed as UUID, not name

All article displays show:
```
Authors: de09b6df-d1d3-4dcb-aa36-f26a72dc9ed9
```

The author's display name ("Alice") is known in the DB but not shown. UUIDs are
meaningless to humans.

#### 6. Inconsistent ID display

- `account whoami` → `de09b6df` (8 chars)
- `account search Alice` → `ID: de09b6df` (8 chars)
- Article display → `de09b6df-d1d3-4dcb-aa36-f26a72dc9ed9` (full UUID)
- `bookmark add P3` → `✓ Bookmarked 3323422e` (8-char prefix, different from input!)
- Follow confirmation → `✓ Now following 1abb6e75` (8 chars, not the name "Bob")

The user types a title or name, gets back a UUID prefix they've never seen.
Confirmations should echo the user's input.

#### 7. `bookmark add P3` returns a different ID than the user typed

```
$ peerpedia bookmark add P3
✓ Bookmarked 3323422e
```

The user typed "P3" (the title). The confirmation shows "3323422e" — a UUID
prefix the user has never seen and can't map back to "P3".

#### 8. "Abstract: none" noise

Every article display includes `Abstract: none` when there's no abstract. This
is visual noise — show nothing instead.

#### 9. `article list --status draft` forces `--mine`

```
$ peerpedia article list --status draft
✗ --status draft requires --mine
```

The user already said they want drafts. Requiring `--mine` is unnecessary
friction. `--status draft` should imply `--mine` automatically.

#### 10. Review comment 200-char minimum with no counter

```
$ peerpedia review submit ... --comment "...199 chars..."
✗ Review comment must be at least 200 characters (got 199)
```

The user has no way to count characters in the terminal. The error tells them
they're 1 character short — but they couldn't know. Provide a character count
during interactive input, or make the editor show length.

#### 11. "Must accept a review invitation" — undiscoverable workflow

```
$ peerpedia review submit 8c9cda37 ...
✗ Must accept a review invitation before submitting a review during sedimentation
```

The user published an article, then tried to self-review. The error mentions
"accept a review invitation" but the user was never told they need an invitation.
The publication workflow is: publish → invite reviewers → they accept → they
review. This sequence is not obvious from the CLI output.

#### 12. "No pending invitation found" — same discoverability issue

```
$ peerpedia review accept 8c9cda37
✗ No pending invitation found for this article
```

The user doesn't know who invited them, or that they need to be invited.
The error should say: "You have not been invited to review this article. Ask the
author to run: peerpedia review invite 8c9cda37 --user @you"

#### 13. Auto-sync warnings on every write command

```
$ peerpedia article create ...
⚠ No PEERPEDIA_SERVER set — auto-sync skipped.

$ peerpedia article publish ...
⚠ No PEERPEDIA_SERVER set — auto-sync skipped.

$ peerpedia follow Bob
⚠ No PEERPEDIA_SERVER set — auto-sync skipped.
⚠ No PEERPEDIA_SERVER set — Social sync (follow) push skipped.
⚠ No PEERPEDIA_SERVER set — social pull skipped.
```

Triple warning for a single `follow` command. For users who never set up a server,
this is persistent noise. Should be shown once and then silenced.

#### 14. Garbled warning text

```
⚠ No PEERPEDIA_SERVER set — Share push push skipped.
```

"push push" — duplicated word in the warning message.

#### 15. SAWarning leaks to user output

```
$ peerpedia article list --feed
SAWarning: Coercing Subquery object into a select() for use in IN();
please pass a select() construct explicitly
```

SQLAlchemy deprecation warning in user-facing output. Should be suppressed.

#### 16. `compile` output has odd line breaks

```
✓ Compiled → 
/Users/chenqimeng/.peerpedia/articles/.../compiled/article.html
Format: markdown
```

The file path is split across lines. "Format: markdown" is confusing — it shows
the input format, not the output format.

#### 17. `article diff HEAD HEAD` — empty result, no guidance

```
$ peerpedia article diff 8c9cda37 HEAD HEAD
╭─ Diff ────────────────────────────────────────────────╮
│ +0  -0                                                │
╰────────────────────────────────────────────────────────╯
```

No message like "These are the same revision — no changes to show." Just empty
output.

#### 18. `maintainer list` shows UUIDs only

```
┃ Maintainer ID ┃
┡━━━━━━━━━━━━━━━┩
│ de09b6df      │
```

No display name, just a UUID prefix. Should show "Alice (de09b6df)".

#### 19. Inconsistent output format

- Successful results: Rich panels with borders
- Error results: Rich formatted `✗` with suggestions
- `account search nonexistent`: plain text "No users match 'nonexistent'"
- `alias list`: plain text "No aliases set."
- `share list`: plain text "No shares in feed."

No visual consistency between empty/error results.

#### 20. `alias set Alice Ally` → confusing error

```
$ peerpedia alias set Alice Ally
✗ You must follow de09b6df-d1d3-4dcb-aa36-f26a72dc9ed9 to set an alias
```

That UUID is Alice's own ID. The user tried to set an alias for themselves.
The error should say "You cannot set an alias for yourself" — not "You must
follow [yourself]."

#### 21. `article create --no-editor` creates empty content

```
── Content ──
---
title: UX Test Article
---
```

The "Content" section shows only YAML frontmatter. Better: "No content yet. Use
`peerpedia article edit <id>` to add content."

#### 22. Scores format in help text is cryptic

```
--scores "orig=4,rigor=3,comp=4,ped=3,imp=4"
```

No explanation of what each dimension means. The user has to memorize
`orig,rigor,comp,ped,imp` or look it up every time.

#### 23. `--json` default is non-obvious

By default, output is JSON (for AI consumption). `--rich` enables human-readable.
But the user types `peerpedia article list` and gets Rich output — because
`--json` defaults to True but Rich output happens when `--json` is explicitly
set? The logic in `cli/__init__.py:109-113` is confusing:

```python
if args.rich:
    args.json = False
else:
    args.json = True   # default: JSON for AI
```

### Shell/REPL Issues

#### 24. REPL `Ctrl+J` submit is unconventional

The REPL uses `Ctrl+J` to submit and `Enter` to insert a newline. This is the
**opposite** of every other REPL (Python, IPython, psql, etc.). Users will hit
Enter expecting submit and get a newline.

#### 25. REPL prompt queries database on every render

`_prompt_text()` in `repl/state.py` calls `count_unread_notifications()` on
**every prompt paint**. That's a DB query on every keystroke cycle. For the
notification badge, this could be refreshed less frequently.

#### 26. REPL dies immediately when stdin is not a TTY

```
Warning: Input is not a terminal (fd=0).
```

This makes scripting or piping to the REPL impossible. Should handle
non-TTY input gracefully or fall back to the CLI parser.

### Edge Cases

#### 27. `review submit` validates comment length before scores format

```
$ peerpedia review submit ... --scores "orig=3" --comment "short"
✗ Review comment must be at least 200 characters (got 62)
```

The scores are invalid too (missing 4 dimensions), but the user only learns that
after fixing the comment length. All validations should run at once.

#### 28. `follow` tries to sync to server even without `--server` flag

```
$ peerpedia follow Bob
⚠ No PEERPEDIA_SERVER set — auto-sync skipped.
⚠ No PEERPEDIA_SERVER set — Social sync (follow) push skipped.
⚠ No PEERPEDIA_SERVER set — social pull skipped.
```

The command succeeds locally (follows Bob), but the user gets three warnings
about server sync they never asked for.

## Severity Summary

| # | Severity | Area | Issue |
|---|---|---|---|
| 1 | 🔴 Critical | schema | Crash — `ValueError` in `_cmd_schema` |
| 2 | 🔴 Critical | CLI | `?Mother` broken by shell glob |
| 3 | 🔴 Critical | merge | Raw SQL traceback exposed |
| — | 🟠 High | Perf | 5s hang on any network-touching command |
| — | 🟠 High | Perf | `server_default` persists dead servers forever |
| — | 🟠 High | Perf | Health check double-invoked (`check_clock_skew` + `is_online`) |
| 4 | 🟡 Medium | UX | `article scan` reports "Published" |
| 5 | 🟡 Medium | UX | Author shown as UUID, not name |
| 9 | 🟡 Medium | UX | `--status draft` forces `--mine` |
| 10 | 🟡 Medium | UX | No character counter for review comments |
| 11 | 🟡 Medium | UX | Review invitation workflow undiscoverable |
| 13 | 🟡 Low | UX | Auto-sync warning noise on every command |
| 14 | 🟡 Low | UX | Duplicated text "Share push push" |
| 15 | 🟡 Low | UX | SAWarning leaks to user |
| 23 | 🟡 Low | UX | `--json` default logic confusing |
| 24 | 🟡 Low | REPL | Ctrl+J submit vs Enter convention |
| 25 | 🟡 Low | REPL | DB query on every prompt render |

## The #1 Performance Fix

Delete or expire the `server_default` file when the server is unreachable:

```
$ rm ~/.peerpedia/server_default
```

After this, commands that don't need a server (like `sync status`) should return
fast. But the root code issue remains — the 5-second timeout + automatic
`check_clock_skew()` on every `_resolve_server_url()` call.

**Recommended:**
1. Drop the health check timeout from 5.0 → 1.5 seconds
2. Cache `is_online()` results for 30 seconds
3. If `server_default` points to a dead server for 3+ consecutive calls, warn
   the user and offer to clear it
4. `sync status` should show cached offline status, not re-probe every time
