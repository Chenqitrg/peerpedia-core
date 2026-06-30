# PeerPedia Core — Complete Diagnostic Code Tree

> **Status**: Architecture refactoring 90% complete (P0 done, P1-P4 pending). 27 boundary tests passing.
> Comprehensive AI-readable project map. Every module, function, and dependency.

## 1. ARCHITECTURE OVERVIEW

```
peerpedia_core/
  app/          Frontend-agnostic user logic
    commands/     Domain handlers (account, article, review, social, sync...)
    commandspec/  CommandSpec types + handlers + registry + schema
    readmodels/   Read-only query helpers for frontend rendering
  cli/          CLI frontend — argparse + Rich output
    cmds/         CLI command handlers (thin adapters → spec.handler)
  repl/         REPL frontend — prompt_toolkit + Rich output
  presentation/ Shared Rich components (console-injected)
  core/         Domain orchestration (articles, reviews, users, sync, merge...)
  storage/      Git backend (git/) + DB backend (db/) + peers
  transport/    P2P protocol + HTTP implementation
  server/       Starlette HTTP server
  config/       Paths + tunable params
  compute/     Pure compute (scoring, reputation, sedimentation)
  types/        Shared types (scores, entities)
  messages.py   Structured message registry
  exceptions.py Central exception hierarchy
  editor.py     Terminal editor + password helpers
  compiler.py   Article compilation
  crypto.py     Ed25519 key utilities
  frontmatter.py YAML frontmatter parser
```

### Command dispatch flow
```
CLI:  cli/parser.py (argparse from CommandSpec) → cli/cmds/* → spec.handler(ctx, args_dict)
REPL: repl/engine.py (shlex + CommandSpec) → spec.handler(ctx, args_dict)
Both: spec.handler → app/commands/* → core/* → storage/*
```

## 2. COMPLETE FILE INVENTORY

| File | Lines | Funcs | Classes | Imports from |
|------|-------|-------|---------|-------------|
| app/__init__.py | 15 | 0 | 0 | app |
| app/commands/__init__.py | 4 | 0 | 0 |  |
| app/commands/account.py | 132 | 8 | 0 | app, core, crypto |
| app/commands/article.py | 241 | 11 | 0 | app, config, core, exceptions, rules, storage |
| app/commands/bundle.py | 100 | 6 | 0 | app, core, exceptions |
| app/commands/dashboard.py | 32 | 3 | 0 | core, storage |
| app/commands/fork.py | 63 | 4 | 0 | app, core |
| app/commands/maintainer.py | 69 | 5 | 0 | app, core |
| app/commands/notification.py | 40 | 2 | 0 | app, core |
| app/commands/review.py | 126 | 7 | 0 | app, core |
| app/commands/social.py | 190 | 13 | 0 | app, core |
| app/commands/sync.py | 156 | 7 | 0 | config, core, exceptions, storage, time, transport |
| app/commandspec/__init__.py | 16 | 0 | 0 | app |
| app/commandspec/handlers.py | 231 | 49 | 0 | app |
| app/commandspec/registry.py | 306 | 3 | 0 | app, types |
| app/commandspec/schema.py | 140 | 12 | 0 | app |
| app/commandspec/types.py | 68 | 0 | 3 | app |
| app/context.py | 112 | 4 | 1 | config, crypto, storage, transport |
| app/parsers.py | 100 | 3 | 0 | exceptions, types |
| app/readmodels/__init__.py | 4 | 0 | 0 |  |
| app/readmodels/articles.py | 69 | 6 | 0 | core, storage |
| app/refs.py | 140 | 13 | 0 | app, core, exceptions, storage |
| app/result.py | 42 | 0 | 2 |  |
| cli/__init__.py | 124 | 4 | 0 | app, cli, config, core |
| cli/bundle_utils.py | 128 | 8 | 0 | app, cli, config, exceptions, transport |
| cli/cmds/__init__.py | 26 | 0 | 0 |  |
| cli/cmds/account.py | 96 | 7 | 0 | app, cli, editor |
| cli/cmds/article.py | 215 | 11 | 0 | app, cli, compiler, editor |
| cli/cmds/fork.py | 39 | 4 | 0 | app, cli |
| cli/cmds/help.py | 33 | 1 | 0 |  |
| cli/cmds/maintainers.py | 49 | 5 | 0 | app, cli |
| cli/cmds/mother.py | 24 | 1 | 0 | cli |
| cli/cmds/notifications.py | 38 | 2 | 0 | app, cli |
| cli/cmds/reviews.py | 85 | 8 | 0 | app, cli, editor |
| cli/cmds/schema.py | 14 | 1 | 0 | app |
| cli/cmds/server.py | 53 | 3 | 0 | app, cli, server |
| cli/cmds/social.py | 146 | 14 | 0 | app, cli |
| cli/cmds/sync.py | 35 | 3 | 0 | app, cli |
| cli/decorators.py | 83 | 4 | 0 | app, cli, config, core, exceptions |
| cli/dispatch.py | 133 | 2 | 0 |  |
| cli/display.py | 181 | 11 | 0 | app, cli, messages, presentation |
| cli/info.py | 246 | 13 | 1 | messages |
| cli/parser.py | 277 | 9 | 3 | app, cli, types |
| cli/session.py | 80 | 6 | 0 | cli, config, crypto |
| repl/__init__.py | 21 | 0 | 0 | repl |
| repl/banner.py | 54 | 1 | 0 | core, repl |
| repl/browse.py | 258 | 25 | 0 | app, core, repl |
| repl/completer.py | 74 | 4 | 1 | app, repl |
| repl/dispatch.py | 134 | 11 | 0 | repl |
| repl/display.py | 140 | 9 | 0 | app, exceptions, messages, presentation, repl |
| repl/engine.py | 216 | 5 | 0 | app, editor, exceptions, repl |
| repl/help.py | 245 | 7 | 0 | app, repl |
| repl/main.py | 134 | 3 | 0 | app, config, core, repl |
| repl/meta.py | 139 | 4 | 0 | app, core, repl |
| repl/state.py | 184 | 5 | 0 | app, config, core |
| repl/wizards.py | 67 | 1 | 0 | repl |
| presentation/__init__.py | 10 | 0 | 0 |  |
| presentation/rich/__init__.py | 4 | 0 | 0 |  |
| presentation/rich/components.py | 112 | 6 | 0 | types |
| core/__init__.py | 196 | 6 | 0 | config, core, frontmatter, storage, types |
| core/articles/__init__.py | 85 | 6 | 0 | core, storage |
| core/articles/_helpers.py | 18 | 1 | 0 | storage |
| core/articles/create.py | 84 | 2 | 0 | config, crypto, frontmatter, storage |
| core/articles/delete.py | 41 | 1 | 0 | config, core, rules, storage |
| core/articles/diff.py | 65 | 5 | 0 | storage |
| core/articles/fork.py | 60 | 1 | 0 | config, core, rules, storage |
| core/articles/publish.py | 98 | 2 | 0 | config, core, rules, storage |
| core/articles/rollback.py | 72 | 1 | 0 | config, core, crypto, rules, storage |
| core/articles/sink.py | 119 | 4 | 0 | compute, config, core, storage, types |
| core/articles/update.py | 107 | 2 | 0 | config, core, crypto, frontmatter, rules, storage |
| core/bookmarks.py | 33 | 3 | 0 | storage |
| core/guards.py | 119 | 5 | 0 | config, exceptions, rules, storage, types |
| core/maintainers.py | 111 | 5 | 0 | exceptions, storage |
| core/merge.py | 143 | 4 | 0 | config, core, exceptions, rules, storage |
| core/notifications.py | 127 | 7 | 0 | storage |
| core/reconcile/__init__.py | 60 | 2 | 0 | core, exceptions, storage |
| core/reconcile/mirror.py | 123 | 5 | 0 | config, core, exceptions, rules, storage, types |
| core/reconcile/score.py | 94 | 4 | 0 | compute, config, storage, types |
| core/reviews/__init__.py | 73 | 2 | 0 | core, storage |
| core/reviews/invite.py | 136 | 4 | 0 | core, exceptions, storage |
| core/reviews/submit.py | 100 | 3 | 0 | config, core, rules, storage |
| core/reviews/thread.py | 159 | 5 | 0 | config, core, crypto, exceptions, names, rules, storage |
| core/shares.py | 49 | 4 | 0 | storage |
| core/sync_article.py | 175 | 9 | 0 | config, core, exceptions, storage, time, transport |
| core/sync_social.py | 154 | 9 | 0 | config, exceptions, storage, transport, types |
| core/users.py | 188 | 20 | 0 | core, crypto, exceptions, storage |
| core/views.py | 100 | 7 | 0 | core, storage |
| storage/__init__.py | 3 | 0 | 0 |  |
| storage/db/__init__.py | 35 | 2 | 0 | storage |
| storage/db/_validators.py | 101 | 10 | 0 | exceptions, storage |
| storage/db/crawler.py | 121 | 3 | 2 | compute, exceptions, storage, types |
| storage/db/crud_alias.py | 83 | 5 | 0 | storage |
| storage/db/crud_article.py | 474 | 26 | 0 | exceptions, storage |
| storage/db/crud_bookmark.py | 45 | 4 | 0 | storage |
| storage/db/crud_citation.py | 54 | 5 | 0 | storage |
| storage/db/crud_maintainer.py | 76 | 4 | 0 | storage |
| storage/db/crud_merge.py | 92 | 7 | 0 | exceptions, storage |
| storage/db/crud_notification.py | 94 | 5 | 0 | exceptions, storage |
| storage/db/crud_review.py | 174 | 6 | 0 | exceptions, storage |
| storage/db/crud_share.py | 83 | 5 | 0 | storage |
| storage/db/crud_user.py | 501 | 28 | 0 | config, exceptions, storage |
| storage/db/engine.py | 169 | 8 | 2 |  |
| storage/db/guards.py | 160 | 15 | 0 | config, exceptions, rules, storage |
| storage/db/ingest.py | 111 | 10 | 0 | storage, types |
| storage/db/models.py | 347 | 15 | 12 | storage, types |
| storage/db/session_utils.py | 43 | 1 | 0 | storage |
| storage/db/state.py | 81 | 3 | 0 | compute, storage, types |
| storage/git/__init__.py | 73 | 0 | 0 | config, exceptions, storage |
| storage/git/ancestor.py | 67 | 3 | 0 | compute, storage |
| storage/git/archive.py | 52 | 3 | 0 | exceptions, storage |
| storage/git/bundle.py | 70 | 3 | 0 | storage |
| storage/git/guards.py | 102 | 10 | 0 | config, crypto, exceptions, storage, types |
| storage/git/merge.py | 139 | 10 | 0 | config, exceptions, storage |
| storage/git/ops.py | 142 | 7 | 0 | config, crypto, storage |
| storage/git/read.py | 292 | 16 | 1 | config, types |
| storage/git/trailers.py | 63 | 3 | 0 | storage |
| storage/locks.py | 122 | 5 | 1 |  |
| storage/peers.py | 195 | 12 | 0 | config, transport |
| transport/__init__.py | 59 | 0 | 1 |  |
| transport/auth.py | 69 | 2 | 1 | crypto |
| transport/guards.py | 79 | 2 | 1 | crypto, exceptions, time, transport |
| transport/http/__init__.py | 2 | 0 | 0 |  |
| transport/http/_core.py | 137 | 11 | 0 | exceptions, transport |
| transport/http/articles.py | 145 | 10 | 0 | exceptions, time, transport |
| transport/http/factory.py | 56 | 1 | 0 | transport |
| transport/http/health.py | 185 | 11 | 0 | config, exceptions, time, transport |
| transport/http/social.py | 203 | 13 | 0 | exceptions, transport |
| server/app.py | 188 | 3 | 0 | config, core, exceptions, server |
| server/middleware/__init__.py | 9 | 0 | 0 | server |
| server/middleware/auth.py | 93 | 2 | 1 | config, core, transport |
| server/middleware/db.py | 37 | 1 | 1 | config, core |
| server/middleware/logging.py | 40 | 1 | 1 | config |
| server/middleware/ratelimit.py | 53 | 2 | 1 | config |
| server/routes/__init__.py | 10 | 0 | 0 | server |
| server/routes/articles.py | 168 | 10 | 0 | config, core, exceptions, server, storage |
| server/routes/peers.py | 37 | 2 | 0 | core |
| server/routes/users.py | 188 | 10 | 0 | core, crypto, exceptions, rules, server |
| server/shared.py | 58 | 4 | 0 | exceptions |
| config/__init__.py | 3 | 0 | 0 |  |
| config/git.py | 73 | 3 | 0 |  |
| config/params.py | 233 | 7 | 7 |  |
| config/paths.py | 94 | 1 | 0 |  |
| types/__init__.py | 4 | 0 | 0 |  |
| types/entities.py | 129 | 8 | 8 |  |
| types/scores.py | 144 | 9 | 2 |  |
| types/status.py | 38 | 2 | 0 | config |
| __init__.py | 3 | 0 | 0 |  |
| __main__.py | 27 | 1 | 0 | cli, repl |
| compiler.py | 329 | 8 | 3 | config, exceptions, frontmatter |
| crypto.py | 236 | 18 | 0 | exceptions |
| editor.py | 95 | 5 | 0 | exceptions |
| exceptions.py | 195 | 0 | 10 |  |
| frontmatter.py | 70 | 4 | 0 |  |
| messages.py | 397 | 2 | 2 |  |
| names.py | 72 | 3 | 0 |  |
| time.py | 73 | 3 | 0 |  |

## 3. COMPLETE FUNCTION INDEX

Legend: ● = public, · = private (_ prefix)

### app/

**app/commands/account.py** (132 lines)

- ● `whoami(ctx: AppContext)` @ L23
- ● `register(ctx: AppContext)` @ L32
- ● `login(ctx: AppContext)` @ L50
- ● `recover(ctx: AppContext)` @ L62
- ● `delete_account(ctx: AppContext)` @ L80
- ● `bootstrap(ctx: AppContext)` @ L90
- ● `search_users(ctx: AppContext)` @ L111
- · `_write_login_session(user, password: str)` @ L124

**app/commands/article.py** (241 lines)

- ● `show(ctx: AppContext)` @ L37
- ● `list_articles(ctx: AppContext)` @ L52
- ● `create(ctx: AppContext)` @ L88
- ● `edit(ctx: AppContext)` @ L114
- ● `publish(ctx: AppContext)` @ L132
- ● `delete(ctx: AppContext)` @ L151
- ● `scan(ctx: AppContext)` @ L164
- ● `diff(ctx: AppContext)` @ L172
- ● `get_source_path(ctx: AppContext)` @ L185
- · `_resolve_user_ref(ctx: AppContext, user_ref: str | None)` @ L201
- · `_article_list_filters(ctx: AppContext)` @ L208

**app/commands/bundle.py** (100 lines)

- ● `sync_status(ctx: AppContext)` @ L17
- ● `sync_pull(ctx: AppContext)` @ L23
- ● `sync_discover(ctx: AppContext)` @ L50
- · `_discover_new_articles(ctx: AppContext, server: str, user_id: str)` @ L69
- · `_sync_all_articles(ctx: AppContext, server: str)` @ L84
- · `_db_has_pending(db)` @ L98

**app/commands/dashboard.py** (32 lines)

- ● `count_user_articles(db: Session, author_id: str)` @ L16
- ● `count_users(db: Session)` @ L25
- ● `publish_ready(db: Session)` @ L30

**app/commands/fork.py** (63 lines)

- ● `fork(ctx: AppContext)` @ L16
- ● `merge_propose(ctx: AppContext)` @ L28
- ● `merge_accept(ctx: AppContext)` @ L40
- ● `merge_withdraw(ctx: AppContext)` @ L55

**app/commands/maintainer.py** (69 lines)

- ● `add(ctx: AppContext)` @ L17
- ● `remove(ctx: AppContext)` @ L29
- ● `list_article_maintainers(ctx: AppContext)` @ L41
- ● `consent(ctx: AppContext)` @ L50
- ● `revoke(ctx: AppContext)` @ L61

**app/commands/notification.py** (40 lines)

- ● `list_notifications(ctx: AppContext)` @ L16
- ● `mark_read_notification(ctx: AppContext)` @ L33

**app/commands/review.py** (126 lines)

- ● `submit(ctx: AppContext)` @ L20
- ● `list_reviews(ctx: AppContext)` @ L38
- ● `reply(ctx: AppContext)` @ L61
- ● `invite_reviewer(ctx: AppContext)` @ L79
- ● `accept(ctx: AppContext)` @ L92
- ● `decline(ctx: AppContext)` @ L103
- ● `rate(ctx: AppContext)` @ L114

**app/commands/social.py** (190 lines)

- ● `follow(ctx: AppContext)` @ L25
- ● `unfollow(ctx: AppContext)` @ L36
- ● `list_following(ctx: AppContext)` @ L47
- ● `list_followers(ctx: AppContext)` @ L57
- ● `bookmark(ctx: AppContext)` @ L70
- ● `unbookmark(ctx: AppContext)` @ L81
- ● `share(ctx: AppContext)` @ L95
- ● `share_list(ctx: AppContext)` @ L110
- ● `unshare(ctx: AppContext)` @ L119
- ● `alias(ctx: AppContext)` @ L133
- ● `alias_list(ctx: AppContext)` @ L144
- ● `unalias(ctx: AppContext)` @ L153
- ● `school(ctx: AppContext)` @ L167

**app/commands/sync.py** (156 lines)

- · `_iter_local_syncable()` @ L32
- · `_skip_if_unknown(transport: Transport, server: str, article_id: str)` @ L37
- ● `sync_one(db: Session, transport: Transport, server: str, article_id: str)` @ L44
- ● `sync_all(db: Session, transport: Transport, server: str)` @ L56
- ● `sync_and_discover(db: Session, transport: Transport, server: str)` @ L71
- ● `sync_all_peers(db: Session, transport: Transport)` @ L88
- ● `announce_to_peers(transport: Transport, public_url: str)` @ L131

**app/commandspec/handlers.py** (231 lines)

- ● `register(ctx: AppContext, args: dict[str, Any])` @ L30
- ● `login(ctx: AppContext, args: dict[str, Any])` @ L33
- ● `recover(ctx: AppContext, args: dict[str, Any])` @ L36
- ● `whoami(ctx: AppContext, args: dict[str, Any])` @ L40
- ● `bootstrap(ctx: AppContext, args: dict[str, Any])` @ L43
- ● `account_delete(ctx: AppContext, args: dict[str, Any])` @ L46
- ● `account_search(ctx: AppContext, args: dict[str, Any])` @ L49
- ● `article_create(ctx: AppContext, args: dict[str, Any])` @ L55
- ● `article_show(ctx: AppContext, args: dict[str, Any])` @ L62
- ● `article_list(ctx: AppContext, args: dict[str, Any])` @ L66
- ● `article_edit(ctx: AppContext, args: dict[str, Any])` @ L77
- ● `article_publish(ctx: AppContext, args: dict[str, Any])` @ L83
- ● `article_delete(ctx: AppContext, args: dict[str, Any])` @ L87
- ● `article_scan(ctx: AppContext, args: dict[str, Any])` @ L90
- ● `article_diff(ctx: AppContext, args: dict[str, Any])` @ L93
- ● `review_submit(ctx: AppContext, args: dict[str, Any])` @ L100
- ● `review_list(ctx: AppContext, args: dict[str, Any])` @ L104
- ● `review_reply(ctx: AppContext, args: dict[str, Any])` @ L107
- ● `review_invite(ctx: AppContext, args: dict[str, Any])` @ L111
- ● `review_accept(ctx: AppContext, args: dict[str, Any])` @ L115
- ● `review_decline(ctx: AppContext, args: dict[str, Any])` @ L118
- ● `review_rate(ctx: AppContext, args: dict[str, Any])` @ L121
- ● `merge_propose(ctx: AppContext, args: dict[str, Any])` @ L128
- ● `merge_accept(ctx: AppContext, args: dict[str, Any])` @ L132
- ● `merge_withdraw(ctx: AppContext, args: dict[str, Any])` @ L136
- ● `follow(ctx: AppContext, args: dict[str, Any])` @ L142
- ● `unfollow(ctx: AppContext, args: dict[str, Any])` @ L145
- ● `following(ctx: AppContext, args: dict[str, Any])` @ L148
- ● `followers(ctx: AppContext, args: dict[str, Any])` @ L151
- ● `school(ctx: AppContext, args: dict[str, Any])` @ L154
- ● `bookmark_add(ctx: AppContext, args: dict[str, Any])` @ L158
- ● `bookmark_remove(ctx: AppContext, args: dict[str, Any])` @ L161
- ● `alias_set(ctx: AppContext, args: dict[str, Any])` @ L164
- ● `alias_remove(ctx: AppContext, args: dict[str, Any])` @ L168
- ● `alias_list(ctx: AppContext, args: dict[str, Any])` @ L171
- ● `share_add(ctx: AppContext, args: dict[str, Any])` @ L174
- ● `share_list(ctx: AppContext, args: dict[str, Any])` @ L178
- ● `share_remove(ctx: AppContext, args: dict[str, Any])` @ L181
- ● `notifications(ctx: AppContext, args: dict[str, Any])` @ L187
- ● `notifications_read(ctx: AppContext, args: dict[str, Any])` @ L190
- ● `sync_status(ctx: AppContext, args: dict[str, Any])` @ L196
- ● `sync_pull(ctx: AppContext, args: dict[str, Any])` @ L199
- ● `sync_discover(ctx: AppContext, args: dict[str, Any])` @ L202
- ● `fork(ctx: AppContext, args: dict[str, Any])` @ L210
- ● `maintainer_add(ctx: AppContext, args: dict[str, Any])` @ L216
- ● `maintainer_remove(ctx: AppContext, args: dict[str, Any])` @ L220
- ● `maintainer_list(ctx: AppContext, args: dict[str, Any])` @ L224
- ● `maintainer_consent(ctx: AppContext, args: dict[str, Any])` @ L227
- ● `maintainer_revoke(ctx: AppContext, args: dict[str, Any])` @ L230

**app/commandspec/registry.py** (306 lines)

- · `_build_index()` @ L286
- ● `find_spec(group: str, action: str | None)` @ L299
- ● `spec_for_cmd_id(cmd_id: str)` @ L304

**app/commandspec/schema.py** (140 lines)

- ● `build(target: str | None)` @ L20
- · `_collect_commands()` @ L33
- · `_make_command()` @ L56
- · `_build_props(arg_specs: list[ArgSpec])` @ L69
- · `_arg_to_property(arg: ArgSpec)` @ L79
- · `_json_type(arg: ArgSpec)` @ L91
- · `_wrap_parameters(props: dict, required: list[str])` @ L103
- · `_format_cli(parts: list[str], props: dict, required: list[str])` @ L110
- · `_cli_arg(name: str, required: bool)` @ L116
- · `_filter_by_target(commands: list[dict], target: str)` @ L122
- · `_die_not_found(target: str)` @ L130
- · `_format_result(commands: list[dict])` @ L138

**app/commandspec/types.py** (68 lines)

- `class ArgSpec` @ L32
- `class CommandSpec` @ L53
- `class CommandGroupSpec` @ L64

**app/context.py** (112 lines)

- `class AppContext` @ L37
- ● `build_context(db: Session)` @ L53
- ● `read_session()` @ L87
- ● `write_session(user_id: str, name: str, private_key_hex: str)` @ L98
- · `_read_session()` @ L110

**app/parsers.py** (100 lines)

- ● `parse_scores(scores_str: str | None)` @ L16
- · `_parse_score_part(part: str, valid_keys: set[str], valid_abbr: set[str])` @ L43
- ● `parse_bootstrap_json(json_str: str)` @ L73

**app/readmodels/articles.py** (69 lines)

- ● `resolve_author_names(db: Session, author_ids: list[str])` @ L28
- ● `list_author_ids(db: Session, article_id: str)` @ L42
- ● `list_author_ids_batch(db: Session, article_ids: list[str])` @ L47
- ● `read_frontmatter(raw: str)` @ L54
- ● `source_path(article_id: str)` @ L59
- ● `list_articles(db: Session)` @ L64

**app/refs.py** (140 lines)

- ● `require_user(ctx: AppContext)` @ L28
- ● `require_article(db: Session, ref: str)` @ L35
- ● `require_user_by_ref(db: Session, ref: str)` @ L43
- ● `require_notification(db: Session, notification_id: str, user_id: str)` @ L61
- ● `guard_name_available(db: Session, name: str)` @ L75
- ● `guard_user_id_available(db: Session, user_id: str)` @ L86
- ● `require_user_by_name(db: Session, name: str | None)` @ L94
- · `_resolve_ref(db, results, ref, lower_guard, format_fn)` @ L108
- · `_ambiguous(ids: str)` @ L122
- ● `format_article_candidates(articles: list[ArticleMetaStorage])` @ L127
- ● `format_user_candidates(users: list[UserStorage])` @ L131
- · `_format_user_id_candidates(users: list[UserStorage])` @ L135
- ● `format_user_candidates_multiline(users: list[UserStorage])` @ L139

**app/result.py** (42 lines)

- `class AppNotice` @ L20
- `class AppResult` @ L31

### cli/

**cli/__init__.py** (124 lines)

- · `_show_dashboard()` @ L38
- · `_show_welcome()` @ L72
- · `_count_users()` @ L89
- ● `main()` @ L99

**cli/bundle_utils.py** (128 lines)

- · `_map_sync_error(e: Exception)` @ L28
- · `_resolve_or_skip(server: str | None)` @ L42
- · `_try_sync(db, server: str | None)` @ L53
- · `_try_sync_all(db)` @ L68
- · `_resolve_server_url(args)` @ L85
- · `_read_saved_server()` @ L98
- · `_check_stale_server(url: str)` @ L111
- · `_save_default_server(url: str)` @ L122

**cli/cmds/account.py** (96 lines)

- · `_cmd_account_register(ctx, args)` @ L19
- · `_cmd_account_login(ctx, args)` @ L30
- · `_cmd_account_recover(ctx, args)` @ L39
- · `_cmd_account_whoami(ctx, args)` @ L52
- · `_cmd_account_bootstrap(ctx, args)` @ L69
- · `_cmd_account_delete(ctx, args)` @ L79
- · `_cmd_account_search(ctx, args)` @ L85

**cli/cmds/article.py** (215 lines)

- · `_get_article_content(args)` @ L34
- · `_compute_edit_diff(old_text: str, new_text: str | None, new_title: str | None, content_changed: bool)` @ L46
- · `_cmd_article_create(ctx, args)` @ L62
- · `_cmd_article_show(ctx, args)` @ L76
- · `_cmd_article_list(ctx, args)` @ L88
- · `_cmd_article_edit(ctx, args)` @ L125
- · `_cmd_article_publish(ctx, args)` @ L155
- · `_cmd_article_delete(ctx, args)` @ L163
- · `_cmd_article_scan(ctx, args)` @ L169
- · `_cmd_article_diff(ctx, args)` @ L177
- · `_cmd_compile(ctx, args)` @ L193

**cli/cmds/fork.py** (39 lines)

- · `_cmd_fork(ctx, args)` @ L13
- · `_cmd_merge_propose(ctx, args)` @ L19
- · `_cmd_merge_accept(ctx, args)` @ L27
- · `_cmd_merge_withdraw(ctx, args)` @ L35

**cli/cmds/help.py** (33 lines)

- · `_cmd_meta_help(args)` @ L13

**cli/cmds/maintainers.py** (49 lines)

- · `_cmd_maintainer_add(ctx, args)` @ L13
- · `_cmd_maintainer_remove(ctx, args)` @ L21
- · `_cmd_maintainer_list(ctx, args)` @ L29
- · `_cmd_maintainer_consent(ctx, args)` @ L37
- · `_cmd_maintainer_revoke(ctx, args)` @ L45

**cli/cmds/mother.py** (24 lines)

- · `_cmd_mother(_args)` @ L14

**cli/cmds/notifications.py** (38 lines)

- · `_cmd_notifications(ctx, args)` @ L16
- · `_cmd_notification_read(ctx, args)` @ L34

**cli/cmds/reviews.py** (85 lines)

- · `_cmd_review_submit(ctx, args)` @ L15
- · `_cmd_review_list(ctx, args)` @ L24
- · `_cmd_review_reply(ctx, args)` @ L32
- · `_cmd_review_invite(ctx, args)` @ L43
- · `_cmd_review_accept(ctx, args)` @ L51
- · `_cmd_review_decline(ctx, args)` @ L59
- · `_cmd_review_rate(ctx, args)` @ L67
- · `_edit_reply(to_user: str)` @ L75

**cli/cmds/schema.py** (14 lines)

- · `_cmd_schema(args)` @ L11

**cli/cmds/server.py** (53 lines)

- · `_cmd_server_start(args)` @ L18
- · `_start_discovery_thread(public_url: str)` @ L40
- · `_run()` @ L43

**cli/cmds/social.py** (146 lines)

- · `_render_user_panels(items: list[dict])` @ L16
- · `_cmd_follow(ctx, args)` @ L34
- · `_cmd_unfollow(ctx, args)` @ L40
- · `_cmd_following(ctx, args)` @ L46
- · `_cmd_followers(ctx, args)` @ L56
- · `_cmd_alias_set(ctx, args)` @ L68
- · `_cmd_alias_remove(ctx, args)` @ L76
- · `_cmd_alias_list(ctx, args)` @ L82
- · `_cmd_bookmark_add(ctx, args)` @ L90
- · `_cmd_bookmark_remove(ctx, args)` @ L96
- · `_cmd_share_add(ctx, args)` @ L104
- · `_cmd_share_list(ctx, args)` @ L114
- · `_cmd_share_remove(ctx, args)` @ L120
- · `_cmd_school(ctx, args)` @ L128

**cli/cmds/sync.py** (35 lines)

- · `_cmd_sync_status(ctx, args)` @ L14
- · `_cmd_sync_pull(ctx, args)` @ L21
- · `_cmd_sync_discover(ctx, args)` @ L28

**cli/decorators.py** (83 lines)

- ● `with_context(func)` @ L33
- · `_rollback_ctx(ctx: AppContext | None)` @ L67
- · `_auto_sync(ctx: AppContext)` @ L77
- ● `wrapper(args)` @ L48

**cli/dispatch.py** (133 lines)

- ● `dispatch(args)` @ L95
- ● `get_cmd_map_for_parser()` @ L110

**cli/display.py** (181 lines)

- · `_print_panel(title: str, content: str | Text)` @ L37
- · `_print_table(headers: list[str], rows: list[list[str]], title: str | None)` @ L42
- · `_status_badge(status: str)` @ L47
- ● `display_article(title: str, status: str, authors: list[str], score: dict | None, abstract: str | None)` @ L52
- ● `display_user(name: str, user_id: str)` @ L69
- ● `display_diff(diff_text: str, stats: dict)` @ L83
- · `_score_lines(score: dict | None, dims: list[str] | None)` @ L124
- · `_stars(score: dict | None, dims: list[str] | None)` @ L129
- ● `display_full_content(raw: str, article_id: str)` @ L137
- ● `display_empty_article_list(code: str)` @ L147
- ● `display_article_meta(db, article)` @ L157

**cli/info.py** (246 lines)

- `class _SafeDict` @ L244
- · `_open_file(path: str)` @ L48
- · `_page(text: str)` @ L58
- · `_ok(what: str)` @ L70
- · `_json_out(data: dict | list)` @ L75
- · `_render_data(data)` @ L80
- · `_render_table(rows: list[dict])` @ L97
- · `_render_key_value_pairs(data: dict)` @ L111
- · `_out()` @ L125
- · `_render_error_out(code: str, m, use_json: bool, fmt: dict)` @ L164
- · `_render_result(args, result)` @ L190
- · `_render_error(args, error)` @ L202
- · `_log(code: str)` @ L219
- · `_format(template: str, fmt: dict)` @ L231

**cli/parser.py** (277 lines)

- `class ArgSpec` @ L98
- `class Command` @ L104
- `class CommandGroup` @ L117
- · `_load_help(name: str)` @ L23
- · `_shared_arg_to_cli(arg: SharedArgSpec)` @ L28
- · `_shared_cmd_to_cli(cs: SharedCommandSpec)` @ L60
- · `_build_commands()` @ L76
- · `_build_epilog()` @ L191
- ● `build_parser()` @ L229
- · `_target_parser(group_parser, subparsers, cmd: Command)` @ L258
- · `_register(p: argparse.ArgumentParser, cmd: Command)` @ L269
- ● `help_epilog(self)` @ L111

**cli/session.py** (80 lines)

- · `_read_session()` @ L20
- · `_write_session(user_id: str, name: str, private_key_hex: str)` @ L34
- · `_get_session_user_id()` @ L45
- · `_get_session_user()` @ L55
- · `_get_session_key()` @ L63
- · `_get_session_pubkey()` @ L73

### repl/

**repl/banner.py** (54 lines)

- ● `show_startup_banner(db, session_data: dict | None)` @ L16

**repl/browse.py** (258 lines)

- · `_get_session_user_id()` @ L22
- · `_build_browser(title: str, render_fn, status_fn, kb)` @ L32
- · `_add_browser_nav_keys(kb: KeyBindings, selected: list[int], n: int)` @ L69
- · `_set_article_context(article)` @ L89
- · `_browse_articles(db, viewer_id: str | None)` @ L96
- · `_browse_school(db)` @ L166
- · `_browse_reviews(db, article_id: str)` @ L207
- · `_(event)` @ L76
- · `_(event)` @ L80
- · `_(event)` @ L85
- · `_formatted_score(v: int)` @ L106
- · `_render()` @ L110
- · `_status_text()` @ L130
- · `_(event)` @ L141
- · `_(event)` @ L146
- · `_(event)` @ L150
- · `_(event)` @ L154
- · `_(event)` @ L158
- · `_render()` @ L177
- · `_status_text()` @ L187
- · `_(event)` @ L198
- · `_render()` @ L220
- · `_status_text()` @ L234
- · `_(event)` @ L246
- · `_(event)` @ L252

**repl/completer.py** (74 lines)

- `class _ReplCompleter` @ L53
- ● `build_flags()` @ L17
- ● `build_command_list()` @ L36
- ● `make_completer(static_words: frozenset[str])` @ L50
- ● `get_completions(self, document, complete_event)` @ L54

**repl/dispatch.py** (134 lines)

- · `_handle_quit(arg: str)` @ L27
- · `_handle_compact(arg: str)` @ L31
- · `_handle_feed(arg: str)` @ L38
- · `_handle_school(arg: str)` @ L43
- · `_handle_write(arg: str)` @ L62
- · `_handle_help(arg: str)` @ L67
- · `_handle_user(arg: str)` @ L72
- · `_handle_article(arg: str)` @ L77
- · `_handle_theme(arg: str)` @ L82
- · `_handle_inbox(arg: str)` @ L87
- · `_dispatch_meta(cmd_str: str)` @ L116

**repl/display.py** (140 lines)

- · `_print_table(headers: list[str], rows: list[list[str]], title: str | None)` @ L32
- ● `display_user(name: str, user_id: str)` @ L37
- · `_score_lines(score: dict | None, dims: list[str] | None)` @ L50
- · `_stars(score: dict | None, dims: list[str] | None)` @ L54
- · `_status_badge(status: str)` @ L58
- · `_print_panel(title: str, content: str)` @ L62
- ● `render_result(result: AppResult)` @ L69
- · `_render_notice(notice)` @ L124
- ● `render_error(error: PeerpediaError)` @ L132

**repl/engine.py** (216 lines)

- · `_parse_args(raw_args: list[str], spec: CommandSpec)` @ L36
- · `_parse_flag(a: str, raw_args: list[str], i: int, spec: CommandSpec)` @ L80
- · `_coerce(val: str, arg: ArgSpec)` @ L103
- ● `execute(cmd_str: str)` @ L126
- · `_iter_all_specs()` @ L212

**repl/help.py** (245 lines)

- · `_meta_help(topic: str)` @ L30
- · `_show_topic_help(topic: str)` @ L77
- · `_find_subcommands_for_group(group: str)` @ L129
- · `_is_section_header(line: str)` @ L137
- · `_render_help_text(text: str)` @ L149
- · `_parse_kv(filepath: Path)` @ L216
- · `_display_help_panel(text: str, title: str, extra_markup: list[str] | None)` @ L232

**repl/main.py** (134 lines)

- ● `run()` @ L38
- · `_(event)` @ L74
- · `_(event)` @ L78

**repl/meta.py** (139 lines)

- · `_meta_user(name)` @ L33
- · `_meta_article(ref: str)` @ L60
- · `_meta_theme(mode: str)` @ L100
- · `_show_inbox()` @ L118

**repl/state.py** (184 lines)

- ● `new_session()` @ L29
- ● `session_scope()` @ L42
- ● `close_db()` @ L61
- · `_prompt_text()` @ L119
- · `_refresh_completions()` @ L157

**repl/wizards.py** (67 lines)

- · `_meta_write(execute)` @ L20

### presentation/

**presentation/rich/components.py** (112 lines)

- ● `score_lines(score: dict | None, dims: list[str] | None)` @ L31
- ● `score_stars(score: dict | None, dims: list[str] | None)` @ L44
- ● `status_badge(status: str)` @ L59
- ● `print_table(console: Console, headers: list[str], rows: list[list[str]], title: str | None)` @ L67
- ● `print_panel(console: Console, title: str, content: str | Text, border_style: str)` @ L78
- ● `display_user(console: Console, name: str, user_id: str)` @ L87

### core/

**core/__init__.py** (196 lines)

- ● `db_repl_init(database_url: str)` @ L31
- ● `db_repl_new_session(database_url: str)` @ L41
- ● `db_repl_dispose()` @ L52
- ● `health_check(database_url: str)` @ L60
- ● `search_articles(db: Session, query: str)` @ L91
- ● `merge_article_meta(db: Session, entries: list[dict])` @ L103

**core/articles/__init__.py** (85 lines)

- ● `get_article(db: Session, article_id: str)` @ L30
- ● `list_articles(db: Session, status: str | set[str] | None, search_query: str | None, author_id: str | None, viewer_id: str | None, bookmarked_by: str | None, id_prefix: str | None, limit: int | None, offset: int)` @ L42
- ● `count_articles(db: Session)` @ L64
- · `_to_set(value: str | set[str] | None)` @ L71
- ● `list_all_article_ids(db: Session)` @ L79
- ● `list_author_ids(db: Session, article_id: str)` @ L83

**core/articles/_helpers.py** (18 lines)

- ● `reset_sink(db: Session, article_id: str, rp: Path, extra_days: int)` @ L15

**core/articles/create.py** (84 lines)

- · `_write_initial_article(rp)` @ L24
- ● `create_article_with_content(db: Session)` @ L32

**core/articles/delete.py** (41 lines)

- ● `delete_article(db: Session, article_id: str)` @ L21

**core/articles/diff.py** (65 lines)

- · `_resolve_head(repo_path: Path)` @ L14
- · `_resolve_offset(repo_path: Path, ref: str)` @ L19
- · `_resolve_hash_prefix(repo_path: Path, ref: str)` @ L31
- ● `resolve_commit_ref(repo_path: Path, ref: str)` @ L41
- ● `diff_article(article_id: str, hash1: str, hash2: str)` @ L56

**core/articles/fork.py** (60 lines)

- ● `fork_article(db: Session, article_id: str, user_id: str)` @ L27

**core/articles/publish.py** (98 lines)

- · `_build_publish_notifications(db: Session, article_id: str, a, user)` @ L29
- ● `publish_article(db: Session, article_id: str, user_id: str, self_review: dict)` @ L50

**core/articles/rollback.py** (72 lines)

- ● `rollback_article(db: Session, article_id: str, target_hash: str, user_id: str, signing_key_bytes: bytes | None, pubkey_hex: str | None)` @ L23

**core/articles/sink.py** (119 lines)

- ● `publish_ready_articles(db: Session)` @ L22
- · `_process_sink_article(db: Session, article)` @ L46
- · `_count_approving_reviews(db: Session, article_id: str, author_ids: list[str])` @ L92
- · `_decide_sink_disposition(article, approval_count: int)` @ L107

**core/articles/update.py** (107 lines)

- · `_rewrite_article_file(rp: Path, a)` @ L28
- ● `update_article_content(db: Session, article_id: str)` @ L45

**core/bookmarks.py** (33 lines)

- ● `add_bookmark(db: Session, user_id: str, article_id: str)` @ L21
- ● `get_bookmarks_for_user(db: Session, user_id: str)` @ L26
- ● `remove_bookmark(db: Session, user_id: str, article_id: str)` @ L31

**core/guards.py** (119 lines)

- ● `guard_invitation_conflicts(db: Session, article_id: str, invited_id: str)` @ L58
- · `_author_has_replied(article_id: str)` @ L70
- ● `guard_closes_trailer(message: str, article_id: str)` @ L85
- ● `verify_commit_signature_and_tofu(db: Session, repo_path: Path, commit: dict, users_by_id: dict)` @ L97
- ● `verify_new_commits(db: Session, repo_path: Path)` @ L111

**core/maintainers.py** (111 lines)

- ● `add_maintainer_to_article(db: Session, article_id: str, user_id: str, caller_id: str)` @ L42
- ● `remove_maintainer_from_article(db: Session, article_id: str, user_id: str, caller_id: str)` @ L63
- ● `list_maintainers(db: Session, article_id: str)` @ L88
- ● `consent_to_publish(db: Session, article_id: str, user_id: str)` @ L97
- ● `revoke_publish_consent(db: Session, article_id: str, user_id: str)` @ L104

**core/merge.py** (143 lines)

- · `_notify_maintainers_except(db, target_id, proposer_id, proposer_name)` @ L68
- ● `accept_merge(db: Session, article_id: str, proposal_id: str, user_id: str)` @ L82
- ● `create_merge_proposal(db: Session, fork_id: str, target_id: str, proposer_id: str)` @ L122
- ● `withdraw_merge_proposal(db: Session, proposal_id: str, user_id: str)` @ L130

**core/notifications.py** (127 lines)

- ● `create_notification(db: Session)` @ L16
- ● `get_notifications(db: Session, user_id: str)` @ L30
- ● `mark_read(db: Session, notification_id: str)` @ L37
- ● `count_unread_notifications(db: Session, user_id: str)` @ L42
- ● `get_notifications_for_user(db: Session, user_id: str)` @ L47
- ● `merge_notifications(db: Session, entries: list[dict])` @ L64
- ● `create_notifications_batch(db: Session, entries: list[dict])` @ L102

**core/reconcile/__init__.py** (60 lines)

- ● `reconcile_all(db: Session, article_id: str)` @ L34
- ● `reconcile_after_sync(db: Session, article_id: str)` @ L44

**core/reconcile/mirror.py** (123 lines)

- ● `reconcile_authors(db: Session, article_id: str, since_hash: str | None)` @ L35
- ● `reconcile_reviews(db: Session, article_id: str)` @ L52
- ● `reconcile_status(db: Session, article_id: str)` @ L73
- ● `reconcile_integrity(db: Session, article_id: str)` @ L85
- · `_repair_db_cache(db: Session, article_id: str, repo_path)` @ L107

**core/reconcile/score.py** (94 lines)

- ● `reconcile_score(db: Session, article_id: str)` @ L27
- · `_build_reviewer_weight_map(reviewer_users)` @ L66
- ● `reconcile_reputation(db: Session, user_id: str)` @ L74
- ● `reconcile_all_reputations(db: Session)` @ L89

**core/reviews/__init__.py** (73 lines)

- ● `get_reviews_for_article(db: Session, article_id: str)` @ L45
- ● `rate_review_helpfulness(db: Session, article_id: str, reviewer_id: str, rater_id: str, score: int)` @ L50

**core/reviews/invite.py** (136 lines)

- ● `invite_reviewer(db: Session, article_id: str, inviter_id: str, invited_id: str)` @ L25
- · `_create_invitation(db, article_id: str, inviter_id: str, invited_id: str)` @ L65
- ● `accept_invitation(db: Session, article_id: str, reviewer_id: str)` @ L82
- ● `decline_invitation(db: Session, article_id: str, reviewer_id: str)` @ L111

**core/reviews/submit.py** (100 lines)

- ● `submit_review(db: Session, article_id: str, reviewer_id: str, scores: dict)` @ L22
- · `_persist_review(db, article_id, reviewer_id, scores, commit_hash)` @ L77
- · `_notify_review_authors(db, article_id, reviewer_id, reviewer_name, author_ids)` @ L92

**core/reviews/thread.py** (159 lines)

- ● `submit_reply(db: Session, article_id: str, user_id: str, reviewer_ref: str, content: str)` @ L27
- ● `write_review_to_git(article_id: str, directory_id: str, scores: dict, comment: str, display_name: str, email: str, signing_key_bytes: bytes | None, pubkey_hex: str | None)` @ L80
- · `_resolve_review_identity(article, user, reviewer_ref)` @ L106
- · `_derive_anonymous_id(article_id: str)` @ L114
- · `_write_thread_message(article_id: str, directory_id: str, content: str, display_name: str, email: str, commit_marker: str)` @ L131

**core/shares.py** (49 lines)

- ● `add_share(db: Session, sharer_id: str, article_id: str)` @ L20
- ● `remove_share(db: Session, sharer_id: str, article_id: str)` @ L30
- ● `get_shares_for_user(db: Session, user_id: str)` @ L35
- ● `get_feed_shares(db: Session, viewer_id: str)` @ L44

**core/sync_article.py** (175 lines)

- ● `sync_article(db: Session, transport: Transport, server: str, article_id: str)` @ L46
- · `_sync_three_way(db: Session, transport: Transport, server: str, article_id: str, merge_base: str | None, local_head: str, server_head: str)` @ L83
- · `_find_merge_base(transport: Transport, server: str, article_id: str, repo_path: Path, server_head: str)` @ L101
- ● `pull_incremental(db: Session, transport: Transport, server: str, article_id: str, since_hash: str | None)` @ L116
- ● `pull_new_article(db: Session, transport: Transport, server: str, article_id: str)` @ L132
- ● `push_incremental(transport: Transport, server: str, article_id: str, since_hash: str, to_hash: str)` @ L141
- · `_upload_article(transport: Transport, server: str, article_id: str)` @ L151
- ● `apply_sync(db: Session, article_id: str, bundle_bytes: bytes)` @ L165
- ● `probe(hash: str)` @ L107

**core/sync_social.py** (154 lines)

- ● `discover_following(db: Session, transport: Transport, server: str, user_id: str)` @ L35
- ● `discover_followers(db: Session, transport: Transport, server: str, user_id: str)` @ L50
- · `_ingest_follow_data(db, server, user_id, data)` @ L65
- ● `discover_articles(db: Session, transport: Transport, server: str, user_id: str, limit: int, offset: int)` @ L76
- ● `discover_shares(db: Session, transport: Transport, server: str, user_id: str)` @ L94
- ● `discover_notifications(db: Session, transport: Transport, server: str, user_id: str)` @ L109
- ● `discover_network(db: Session, transport: Transport, server: str, start_user_id: str, depth: int, max_users: int)` @ L124
- · `_fetch_with_retry(server: str, user_id: str)` @ L138
- · `_discover_articles_fn(db, srv, uid)` @ L145

**core/users.py** (188 lines)

- ● `create_user(db: Session)` @ L39
- ● `create_user_stub(db: Session)` @ L44
- ● `get_user(db: Session, user_ref: str)` @ L58
- ● `list_users_by_name(db: Session, name: str)` @ L63
- ● `update_user_public_key(db: Session, user_id: str, pubkey_hex: str)` @ L68
- ● `update_user_salt(db: Session, user_id: str, salt_hex: str)` @ L82
- ● `follow_user(db: Session, follower_id: str, followed_id: str)` @ L87
- ● `unfollow_user(db: Session, follower_id: str, followed_id: str)` @ L105
- ● `is_following(db: Session, follower_id: str, followed_id: str)` @ L110
- ● `get_followers(db: Session, user_id: str)` @ L115
- ● `get_following(db: Session, user_id: str)` @ L120
- ● `get_top_users_by_followers(db: Session, limit: int)` @ L125
- ● `search_users(db: Session, query: str, limit: int | None, offset: int)` @ L133
- ● `list_users(db: Session)` @ L138
- ● `increment_failed_login(db: Session, user_id: str)` @ L143
- ● `reset_failed_login(db: Session, user_id: str)` @ L148
- ● `soft_delete_user(db: Session, user_id: str)` @ L153
- ● `require_authenticable_user(user: UserStorage)` @ L161
- ● `verify_user_password(db: Session, user: UserStorage, password: str)` @ L173
- ● `find_users(db: Session, ref: str)` @ L182

**core/views.py** (100 lines)

- ● `get_article_view(db: Session, article_id: str)` @ L22
- ● `list_article_views(db: Session)` @ L30
- ● `get_user_view(db: Session, user_id: str)` @ L59
- ● `get_following_views(db: Session, user_id: str)` @ L67
- ● `get_follower_views(db: Session, user_id: str)` @ L72
- ● `list_user_article_views(db: Session, user_id: str)` @ L77
- · `_batch_author_ids(db: Session, article_ids: list[str])` @ L98

### storage/

**storage/db/__init__.py** (35 lines)

- ● `db_session(database_url: str)` @ L19
- ● `db_repl_setup(database_url: str)` @ L24

**storage/db/_validators.py** (101 lines)

- ● `require_not_same(a: str, b: str)` @ L22
- ● `require_alias_nonempty(alias: str)` @ L31
- ● `require_title_nonempty(title: str)` @ L37
- ● `require_helpfulness_score_range(score: int)` @ L46
- ● `require_signing_key(key_bytes: bytes | None, pubkey_hex: str | None, action: str)` @ L55
- ● `require_keys(entries: list[dict[str, object]])` @ L64
- ● `validate_follow_entries(entries: list[dict[str, object]], source_id: str, label: str)` @ L72
- ● `require_draft_status(article: ArticleMetaStorage)` @ L86
- ● `require_sedimentation(article: ArticleMetaStorage)` @ L92
- ● `require_merge_proposal_open(mp: MergeProposalStorage)` @ L98

**storage/db/crawler.py** (121 lines)

- `class CrawlResult` @ L24
- `class _NodeIngestResult` @ L32
- · `_bfs_walk(db: Session, server: str, start_user_id: str)` @ L38
- · `_fetch_ingest_node(db: Session, server: str, user_id: str, fetch_fn, discover_fn, errors: list[dict[str, str]])` @ L77
- ● `get_neighbors(user_id: str)` @ L53

**storage/db/crud_alias.py** (83 lines)

- ● `set_alias(session: Session, owner_id: str, target_id: str, alias: str)` @ L13
- ● `remove_alias(session: Session, owner_id: str, target_id: str)` @ L32
- ● `get_alias_for(session: Session, owner_id: str, target_id: str)` @ L42
- ● `list_aliases(session: Session, owner_id: str)` @ L50
- ● `resolve_username_or_alias(session: Session, owner_id: str, name: str)` @ L60

**storage/db/crud_article.py** (474 lines)

- ● `add_article_authors(session: Session, article_id: str, author_ids: list[str])` @ L60
- ● `set_article_authors(session: Session, article_id: str, author_ids: list[str])` @ L83
- ● `list_author_ids(session: Session, article_id: str)` @ L89
- ● `list_author_ids_batch(session: Session, article_ids: list[str])` @ L95
- ● `list_articles_by_author(session: Session, author_id: str)` @ L115
- ● `create_article(session: Session, authors: list[str], title: str, status: str)` @ L128
- ● `create_article_from_orm(session: Session, article: ArticleMetaStorage, author_ids: list[str])` @ L144
- ● `ensure_article_stub(session: Session, data: dict[str, object])` @ L163
- ● `get_article(session: Session, article_id: str)` @ L187
- ● `list_articles(session: Session, statuses: set[str] | None, search_query: str | None, id_prefix: str | None, author_ids: set[str] | None, viewer_id: str | None, bookmarked_by: str | None, limit: int | None, offset: int)` @ L192
- ● `list_all_article_ids(session: Session)` @ L236
- ● `count_articles(session: Session, statuses: set[str] | None, author_id: str | None)` @ L240
- ● `update_article_compiled(session: Session, article_id: str, html_format: str, output: str | None, pages: list[str] | None)` @ L250
- ● `update_article_status(session: Session, article_id: str, new_status: str)` @ L275
- ● `update_article_score(session: Session, article_id: str, score: dict[str, float])` @ L293
- ● `increment_fork_count(session: Session, article_id: str)` @ L303
- ● `decrement_fork_count(session: Session, article_id: str)` @ L313
- ● `set_sink_start(session: Session, article_id: str, duration_days: int)` @ L325
- ● `delete_article(session: Session, article_id: str)` @ L342
- ● `extend_sink(session: Session, article_id: str, extra_days: int, max_days: int)` @ L369
- ● `get_article_by_fork_and_author(session: Session, forked_from: str, author_id: str)` @ L392
- ● `update_witnessed_at(session: Session, article_id: str)` @ L407
- · `_get_article_or_raise(session: Session, article_id: str)` @ L430
- ● `add_publish_consent(session: Session, article_id: str, user_id: str)` @ L438
- ● `remove_publish_consent(session: Session, article_id: str, user_id: str)` @ L452
- ● `clear_publish_consents(session: Session, article_id: str)` @ L465

**storage/db/crud_bookmark.py** (45 lines)

- ● `add_bookmark(session: Session, user_id: str, article_id: str)` @ L11
- ● `remove_bookmark(session: Session, user_id: str, article_id: str)` @ L24
- ● `is_bookmarked(session: Session, user_id: str, article_id: str)` @ L32
- ● `get_bookmarks_for_user(session: Session, user_id: str)` @ L37

**storage/db/crud_citation.py** (54 lines)

- ● `create_or_update_citation(session: Session, from_id: str, to_id: str, forward: float, backward: float)` @ L12
- ● `get_citation(session: Session, from_id: str, to_id: str)` @ L37
- ● `get_citations(session: Session, article_id: str)` @ L42
- ● `get_cites(session: Session, article_id: str)` @ L47
- ● `get_cited_by(session: Session, article_id: str)` @ L52

**storage/db/crud_maintainer.py** (76 lines)

- ● `add_maintainer(session: Session, article_id: str, user_id: str)` @ L22
- ● `remove_maintainer(session: Session, article_id: str, user_id: str)` @ L39
- ● `get_maintainer_ids(session: Session, article_id: str)` @ L55
- ● `is_maintainer(session: Session, article_id: str, user_id: str)` @ L66

**storage/db/crud_merge.py** (92 lines)

- ● `create_merge_proposal(session: Session, fork_id: str, target_id: str, proposer_id: str)` @ L16
- ● `get_merge_proposal(session: Session, proposal_id: str)` @ L51
- ● `get_merge_proposals_for_article(session: Session, article_id: str)` @ L56
- · `_resolve(session: Session, proposal_id: str, new_status: str)` @ L66
- ● `accept_merge_proposal(session: Session, proposal_id: str)` @ L77
- ● `reject_merge_proposal(session: Session, proposal_id: str)` @ L82
- ● `withdraw_merge_proposal(session: Session, proposal_id: str)` @ L87

**storage/db/crud_notification.py** (94 lines)

- ● `create_notification(session: Session)` @ L12
- ● `ensure_notification(session: Session)` @ L31
- ● `get_notifications(session: Session, user_id: str)` @ L64
- ● `mark_read(session: Session, notification_id: str)` @ L78
- ● `count_unread_notifications(session: Session, user_id: str)` @ L88

**storage/db/crud_review.py** (174 lines)

- ● `upsert_review(session: Session, article_id: str, commit_hash: str, reviewer_id: str, scores: dict[str, float])` @ L44
- ● `get_reviews_for_article(session: Session, article_id: str)` @ L96
- ● `get_pending_invitation(session: Session, article_id: str, reviewer_id: str)` @ L109
- ● `get_accepted_invitation(session: Session, article_id: str, reviewer_id: str)` @ L126
- ● `update_review_status(session: Session, review: ReviewMetaStorage, status: str)` @ L143
- ● `get_review(session: Session, article_id: str, reviewer_id: str, scope: str, commit_hash: str)` @ L157

**storage/db/crud_share.py** (83 lines)

- ● `add_share(session: Session, sharer_id: str, article_id: str)` @ L11
- ● `remove_share(session: Session, sharer_id: str, article_id: str)` @ L32
- ● `is_shared(session: Session, sharer_id: str, article_id: str)` @ L42
- ● `get_shares_for_user(session: Session, user_id: str)` @ L49
- ● `get_shares_by_followed(session: Session, viewer_id: str)` @ L62

**storage/db/crud_user.py** (501 lines)

- ● `create_user(session: Session, name: str, public_key: str | None)` @ L64
- ● `create_user_stub(session: Session, user_id: str, name: str, public_key: str, salt: str)` @ L83
- ● `ensure_user(session: Session, user_id: str, name: str)` @ L111
- ● `get_user(session: Session, user_id: str)` @ L136
- ● `list_users_by_name(session: Session, name: str)` @ L141
- ● `list_users(session: Session, limit: int | None)` @ L148
- ● `search_users(session: Session, query: str)` @ L158
- ● `list_users_by_ids(session: Session, user_ids: set[str])` @ L173
- ● `update_user_public_key(session: Session, user_id: str, pubkey_hex: str)` @ L194
- ● `set_user_pubkey_tofu(session: Session, user_id: str, pubkey_hex: str)` @ L204
- ● `update_user_salt(session: Session, user_id: str, salt_hex: str)` @ L227
- ● `update_user_reputation(session: Session, user_id: str, reputation: dict[str, float])` @ L237
- ● `increment_failed_login(session: Session, user_id: str)` @ L252
- ● `reset_failed_login(session: Session, user_id: str)` @ L269
- ● `soft_delete_user(session: Session, user_id: str)` @ L290
- ● `follow_user(session: Session, follower_id: str, followed_id: str)` @ L314
- · `_soft_delete_follow_row(row: FollowStorage)` @ L334
- ● `follow_users(session: Session, follower_id: str, followed_ids: set[str])` @ L339
- ● `add_followers(session: Session, followed_id: str, follower_ids: set[str])` @ L353
- ● `set_following(session: Session, follower_id: str, followed_ids: set[str])` @ L367
- ● `set_followers(session: Session, followed_id: str, follower_ids: set[str])` @ L391
- ● `unfollow_user(session: Session, follower_id: str, followed_id: str)` @ L415
- ● `is_following(session: Session, follower_id: str, followed_id: str)` @ L432
- ● `get_followers(session: Session, user_id: str)` @ L441
- ● `get_following(session: Session, user_id: str)` @ L451
- ● `get_follower_count(session: Session, user_id: str)` @ L461
- ● `get_following_count(session: Session, user_id: str)` @ L470
- ● `get_top_users_by_followers(session: Session, limit: int)` @ L479

**storage/db/engine.py** (169 lines)

- `class Base` @ L56
- `class _JSONType` @ L29
- · `_make_json_type()` @ L26
- ● `get_engine(database_url: str)` @ L65
- ● `init_db(engine: Engine)` @ L93
- ● `migrate_db(engine: Engine)` @ L98
- ● `get_session(engine: Engine)` @ L160
- ● `process_bind_param(self, value, dialect)` @ L33
- ● `process_result_value(self, value, dialect)` @ L38
- · `_set_sqlite_pragma(dbapi_connection, _connection_record)` @ L83

**storage/db/guards.py** (160 lines)

- ● `require_user(db: Session, user_id: str)` @ L32
- ● `require_article(db: Session, article_id: str)` @ L41
- ● `require_maintainer(db: Session, article_id: str, user_id: str)` @ L50
- ● `assert_caller_is_maintainer(db: Session, article_id: str, caller_id: str)` @ L56
- ● `guard_not_already_maintainer(db: Session, article_id: str, user_id: str)` @ L68
- ● `require_authors_exist(db: Session, author_ids: list[str])` @ L74
- ● `require_following_for_alias(db: Session, owner_id: str, target_id: str)` @ L80
- ● `require_review(db: Session, article_id: str, reviewer_id: str)` @ L86
- ● `authorize_article_action(db: Session, article_id: str, user_id: str)` @ L95
- ● `guard_sedimentation_limit(db: Session, user_id: str)` @ L106
- ● `require_invitation(db: Session, article_id: str, reviewer_id: str)` @ L115
- ● `guard_invitation_not_declined(db: Session, article_id: str, reviewer_id: str)` @ L121
- ● `guard_invitation_not_accepted(db: Session, article_id: str, reviewer_id: str)` @ L134
- ● `guard_not_last_maintainer(db: Session, article_id: str, caller_id: str, user_id: str)` @ L140
- ● `require_open_proposal(db: Session, proposal_id: str, article_id: str)` @ L149

**storage/db/ingest.py** (111 lines)

- ● `ingest_users(db: Session, entries: list[UserExchange])` @ L30
- ● `ingest_following(db: Session, follower_id: str, entries: list[FollowExchange])` @ L37
- ● `sync_following(db: Session, follower_id: str, entries: list[FollowExchange])` @ L43
- ● `ingest_followers(db: Session, followed_id: str, entries: list[FollowExchange])` @ L51
- ● `sync_followers(db: Session, followed_id: str, entries: list[FollowExchange])` @ L57
- ● `ingest_articles(db: Session, entries: list[ArticleMetaExchange])` @ L65
- ● `ingest_bookmarks(db: Session, user_id: str, entries: list[BookmarkExchange])` @ L74
- ● `ingest_maintainers(db: Session, article_id: str, entries: list[MaintainerExchange])` @ L81
- ● `ingest_shares(db: Session, user_id: str, entries: list[ShareExchange])` @ L88
- ● `ingest_notifications(db: Session, user_id: str, entries: list[NotificationExchange])` @ L97

**storage/db/models.py** (347 lines)

- `class ArticleMetaStorage` @ L36
- `class ReviewMetaStorage` @ L101
- `class ArticleAuthorStorage` @ L139
- `class ScriptMaintainerStorage` @ L152
- `class UserStorage` @ L165
- `class FollowStorage` @ L214
- `class AliasStorage` @ L231
- `class ShareStorage` @ L244
- `class BookmarkStorage` @ L270
- `class NotificationStorage` @ L283
- `class MergeProposalStorage` @ L323
- `class CitationStorage` @ L339
- · `_new_id()` @ L25
- · `_utcnow()` @ L29
- ● `to_dict(self)` @ L65
- ● `from_exchange(cls, e: ArticleMetaExchange)` @ L82
- ● `to_exchange(self)` @ L90
- ● `from_exchange(cls, e: ReviewExchange)` @ L123
- ● `to_exchange(self)` @ L129
- ● `to_dict(self)` @ L184
- ● `from_exchange(cls, e: UserExchange)` @ L198
- ● `to_exchange(self)` @ L204
- ● `from_exchange(cls, e: ShareExchange)` @ L257
- ● `to_exchange(self)` @ L261
- ● `to_dict(self)` @ L296
- ● `from_exchange(cls, e: NotificationExchange)` @ L309
- ● `to_exchange(self)` @ L314

**storage/db/session_utils.py** (43 lines)

- ● `db_session_scope(database_url: str)` @ L23

**storage/db/state.py** (81 lines)

- ● `extract_reputation_state(db: Session, user_id: str)` @ L22
- · `_build_article_review_maps(db: Session, articles, author_map: dict)` @ L40
- · `_build_user_snapshot_map(db: Session, user_id: str, reviews_map: dict)` @ L66

**storage/git/ancestor.py** (67 lines)

- ● `find_common_ancestor(repo_path: Path, probe: Callable[[str], bool | None], server_head: str | None, k: int, max_depth: int, retries: int)` @ L16
- · `_hash_at(dist: int)` @ L48
- ● `probe_at(dist: int)` @ L52

**storage/git/archive.py** (52 lines)

- ● `ingest_article(repo_path: Path, payload: dict[str, str])` @ L12
- ● `ingest_article_repo(repo_path: Path, payload: dict[str, str])` @ L24
- ● `pack_article_repo(repo_path: Path)` @ L43

**storage/git/bundle.py** (70 lines)

- ● `get_head(repo_path: Path)` @ L14
- ● `ingest_bundle(repo_path: Path, bundle_bytes: bytes)` @ L27
- ● `create_bundle(repo_path: Path, since_hash: str | None)` @ L55

**storage/git/guards.py** (102 lines)

- ● `require_valid_article_status(status: str)` @ L20
- ● `require_commit_signing_key(signing_key, pubkey_hex: str | None, author_email: str)` @ L26
- ● `require_signing_key_for_pubkey(signing_key, pubkey_hex: str | None)` @ L33
- ● `extract_pubkey_from_message(message: str)` @ L39
- ● `verify_commit_signature(repo_path: Path, commit_hash: str, pubkey_ssh_line: str, author_email: str)` @ L49
- ● `assert_repo_on_main(repo_path: Path)` @ L63
- ● `require_commit_pubkey_signature(repo_path: Path, commit_hash: str, message: str, author_email: str)` @ L68
- ● `guard_not_empty(repo: git.Repo)` @ L79
- ● `require_article_repo(article_id: str)` @ L85
- ● `require_review_scores(repo_path: Path, reviewer_dir: str, article_id: str)` @ L94

**storage/git/merge.py** (139 lines)

- ● `merge_git_repos(target: Path, fork: Path, author_name: str)` @ L22
- ● `merge_fetch_head(repo_path: Path)` @ L56
- · `_resolve_fork_ref(target_repo: git.Repo, remote_name: str, fork_name: str)` @ L72
- · `_merge_env(author_name: str)` @ L83
- · `_abort_merge(repo: git.Repo)` @ L94
- · `_cleanup_remote(repo: git.Repo, remote_name: str)` @ L102
- ● `clone_article_repo(src: Path, dst: Path)` @ L113
- ● `checkout_files(repo_path: Path, commit_hash: str)` @ L119
- ● `reset_to_commit(repo_path: Path, commit_hash: str)` @ L124
- ● `rollback_to(repo_path: Path, target_hash: str | None, new_hash: str)` @ L129

**storage/git/ops.py** (142 lines)

- ● `init_article_repo(repo_path: Path)` @ L23
- ● `is_repo_dirty(repo_path: Path)` @ L40
- ● `commit_article(repo_path: Path, message: str, author_name: str, author_email: str, signing_key: Path | None, pubkey_hex: str | None)` @ L48
- ● `commit_status_marker(repo_path: Path, status: str)` @ L85
- · `_commit_signed(repo, signing_key, author_email, author_name, full_message)` @ L97
- · `_write_ssh_pubkey(private_key_path: Path, pub_path: Path)` @ L116
- ● `delete_article_repo(repo_path: Path)` @ L134

**storage/git/read.py** (292 lines)

- `class CommitInfo` @ L22
- ● `assert_on_main(repo: git.Repo)` @ L34
- ● `get_commit_history(repo_path: Path, max_count: int, since_hash: str | None)` @ L63
- ● `read_status_from_git(repo_path: Path)` @ L103
- ● `get_commit_authors(repo_path: Path, since_hash: str | None)` @ L112
- · `_patch_text(d)` @ L134
- · `_count_diff_lines(patch: str)` @ L143
- ● `get_diff_between(repo_path: Path, hash1: str, hash2: str)` @ L154
- ● `get_head_commit(repo_path: Path)` @ L204
- ● `get_head_hash(repo_path: Path)` @ L213
- ● `get_head_or_none(repo_path: Path)` @ L218
- ● `resolve_article_format(repo_path: Path)` @ L229
- ● `article_source_path(article_id: str)` @ L240
- ● `is_ancestor(repo_path: Path, maybe_ancestor: str)` @ L250
- ● `read_article_source(repo_path: Path)` @ L261
- ● `list_review_dirs(repo_path: Path)` @ L276
- ● `read_review_scores(repo_path: Path, reviewer_dir: str)` @ L284

**storage/git/trailers.py** (63 lines)

- ● `parse_closes_trailer(commit_message: str)` @ L25
- ● `validate_closes_target(article_id: str, reviewer_dir: str, thread_num: int)` @ L36
- ● `list_review_threads(article_id: str)` @ L45

**storage/locks.py** (122 lines)

- `class _TrackedLock` @ L35
- · `_maybe_evict()` @ L86
- ● `get_article_lock(article_id: str)` @ L106
- ● `acquire(self, blocking: bool, timeout: float)` @ L49
- ● `release(self)` @ L60
- ● `locked(self)` @ L65

**storage/peers.py** (195 lines)

- · `_ensure_backoff_hydrated()` @ L30
- · `_load_peers_raw()` @ L38
- · `_save_peers_raw(peers: list)` @ L51
- · `_is_peer_backoff(url: str)` @ L58
- · `_peer_failed(url: str)` @ L73
- · `_peer_succeeded(url: str)` @ L86
- · `_persist_backoff()` @ L94
- · `_hydrate_backoff()` @ L106
- ● `get_known_peers()` @ L127
- ● `add_peer(url: str)` @ L151
- ● `merge_peers(transport: Transport, server_url: str)` @ L161
- ● `record_peer_result(url: str, success: bool)` @ L186

### transport/

**transport/__init__.py** (59 lines)

- `class Transport` @ L18

**transport/auth.py** (69 lines)

- `class AuthResult` @ L30
- ● `sign_auth_header(method: str, path: str, user_id: str, private_key_bytes: bytes, pubkey_hex: str)` @ L38
- ● `build_auth_header(method: str, path: str, user_id: str, private_key_bytes: bytes | None, pubkey_hex: str)` @ L59

**transport/guards.py** (79 lines)

- `class _ParsedHeader` @ L19
- · `_parse_auth_header(header_value: str)` @ L28
- ● `verify_auth_header(header_value: str, method: str, path: str)` @ L45

**transport/http/_core.py** (137 lines)

- · `_get_client()` @ L22
- ● `close_client()` @ L35
- · `_article_path(article_id: str, action: str)` @ L49
- · `_user_path(user_id: str, action: str)` @ L55
- · `_api_path(action: str)` @ L61
- · `_encode_body(data: dict)` @ L66
- · `_require_json_or_none(resp: httpx.Response, server: str, context: str)` @ L71
- · `_post(server: str, path: str, body_dict: dict, user_id: str)` @ L89
- · `_get(server: str, path: str, user_id: str)` @ L104
- · `_call(method: str, server: str, path: str, user_id: str, context: str)` @ L118
- · `_require_ok_or_404(resp: httpx.Response, server: str, context: str)` @ L128

**transport/http/articles.py** (145 lines)

- · `_ancestor_probe(server: str, article_id: str, hash: str)` @ L25
- · `_fetch_head(server: str, article_id: str)` @ L36
- · `_push_bundle(server: str, article_id: str, bundle_bytes: bytes)` @ L44
- · `_fetch_bundle(server: str, article_id: str, since_hash: str | None)` @ L59
- · `_fetch_repo(server: str, article_id: str)` @ L76
- · `_push_repo(server: str, article_id: str, bundle_b64: str)` @ L84
- · `_fetch_source(server: str, article_id: str)` @ L99
- · `_fetch_search(server: str, user_id: str, q: str | None, status: str | None, limit: int, offset: int)` @ L112
- · `_fetch_meta(server: str, article_id: str)` @ L128
- · `_fetch_user_articles(server: str, user_id: str, limit: int, offset: int)` @ L135

**transport/http/factory.py** (56 lines)

- ● `from_http()` @ L28

**transport/http/health.py** (185 lines)

- · `_read_file_cache()` @ L47
- · `_write_file_cache(data: dict[str, tuple[float, bool, int | None]])` @ L60
- ● `clear_health_cache()` @ L73
- · `_probe(server_url: str, timeout: float)` @ L82
- · `_check_health_cache(server_url: str, now: float, ttl: float)` @ L101
- · `_lookup_cache(store: dict[str, tuple[float, bool, int | None]], server_url: str, now: float, ttl: float)` @ L116
- · `_fetch_health(server_url: str, timeout: float)` @ L129
- · `_write_health_cache(server_url: str, now: float, online: bool, server_ts: int | None)` @ L144
- ● `is_online(server_url: str, timeout: float)` @ L155
- ● `check_clock_skew(server_url: str, timeout: float)` @ L164
- · `_prune_cache(data: dict)` @ L179

**transport/http/social.py** (203 lines)

- · `_fetch_following(server: str, user_id: str)` @ L25
- · `_fetch_followers(server: str, user_id: str)` @ L37
- · `_push_follow(server: str, follower_id: str, followed_id: str)` @ L49
- · `_push_unfollow(server: str, follower_id: str, followed_id: str)` @ L62
- · `_push_key_rotation(server: str, user_id: str, new_pubkey_hex: str)` @ L86
- · `_push_share(server: str, sharer_id: str, article_id: str, recipient_id: str | None, comment: str | None)` @ L104
- · `_push_share_remove(server: str, sharer_id: str, article_id: str)` @ L120
- · `_fetch_shares(server: str, user_id: str)` @ L134
- · `_fetch_notifications(server: str, user_id: str)` @ L151
- · `_fetch_peers(server: str)` @ L163
- · `_push_peer_registration(server: str, own_url: str)` @ L175
- · `_fetch_user(server: str, user_id: str)` @ L182
- · `_fetch_school(server: str, limit: int)` @ L188

### server/

**server/app.py** (188 lines)

- · `_health(request: Request)` @ L103
- · `_error_handler(request: Request, exc: Exception)` @ L137
- ● `create_app()` @ L168

**server/middleware/auth.py** (93 lines)

- `class AuthMiddleware` @ L37
- ● `dispatch(self, request: Request, call_next)` @ L44
- · `_unauthorized(self, detail: str)` @ L89

**server/middleware/db.py** (37 lines)

- `class DBSessionMiddleware` @ L21
- ● `dispatch(self, request: Request, call_next)` @ L24

**server/middleware/logging.py** (40 lines)

- `class AuditLogMiddleware` @ L24
- ● `dispatch(self, request: Request, call_next)` @ L27

**server/middleware/ratelimit.py** (53 lines)

- `class RateLimitMiddleware` @ L20
- · `_client_ip(request: Request)` @ L36
- ● `dispatch(self, request: Request, call_next)` @ L41

**server/routes/articles.py** (168 lines)

- · `_head(request: Request)` @ L42
- · `_bundle(request: Request)` @ L51
- · `_sync(request: Request)` @ L61
- · `_ancestor(request: Request)` @ L77
- · `_push_article_repo(request: Request)` @ L85
- · `_article(request: Request)` @ L97
- · `_history(request: Request)` @ L111
- · `_search(request: Request)` @ L125
- · `_source(request: Request)` @ L136
- · `_repo(request: Request)` @ L147

**server/routes/peers.py** (37 lines)

- · `_peers_endpoint(request: Request)` @ L19
- · `_register_peer(request: Request)` @ L24

**server/routes/users.py** (188 lines)

- · `_following(request: Request)` @ L43
- · `_followers(request: Request)` @ L49
- · `_follow(request: Request)` @ L55
- · `_rotate_key(request: Request)` @ L69
- · `_articles(request: Request)` @ L101
- · `_push_share(request: Request)` @ L114
- · `_get_shares(request: Request)` @ L133
- · `_get_notifications(request: Request)` @ L140
- · `_user_detail(request: Request)` @ L147
- · `_school(request: Request)` @ L168

**server/shared.py** (58 lines)

- · `_validate_id(value: str, label: str)` @ L19
- · `_require_field(payload: dict, name: str)` @ L31
- · `_ok_response(data: dict | None)` @ L43
- · `_parse_pagination(request, default_limit: int, max_limit: int)` @ L51

### config/

**config/git.py** (73 lines)

- ● `make_article_gitignore()` @ L37
- ● `ssh_sign_env(allowed_signers: Path, signing_key: Path)` @ L50
- ● `ssh_verify_env(allowed_signers: Path)` @ L64

**config/params.py** (233 lines)

- `class SinkParams` @ L103
- `class ScoreParams` @ L121
- `class ReputationParams` @ L148
- `class CommentParams` @ L160
- `class DiscoveryParams` @ L168
- `class ServerParams` @ L179
- `class Params` @ L214
- ● `make_peerpedia_email(local_part: str)` @ L20
- ● `extract_user_id_from_email(email: str)` @ L31
- ● `article_format_to_ext(fmt: str)` @ L73
- ● `article_ext_to_format(ext: str)` @ L84
- ● `article_filename(ext: str)` @ L93
- ● `score_to_sink_multiplier(self, avg_score: float)` @ L130
- ● `no_review_penalty(self)` @ L138

**config/paths.py** (94 lines)

- ● `article_repo_path(article_id: str)` @ L35

### types/

**types/entities.py** (129 lines)

- `class UserExchange` @ L16
- `class FollowExchange` @ L32
- `class ArticleMetaExchange` @ L41
- `class ReviewExchange` @ L68
- `class BookmarkExchange` @ L86
- `class MaintainerExchange` @ L95
- `class ShareExchange` @ L104
- `class NotificationExchange` @ L117
- ● `from_json(cls, d: dict)` @ L23
- ● `from_json(cls, d: dict)` @ L36
- ● `from_json(cls, d: dict)` @ L57
- ● `from_json(cls, d: dict)` @ L77
- ● `from_json(cls, d: dict)` @ L90
- ● `from_json(cls, d: dict)` @ L99
- ● `from_json(cls, d: dict)` @ L110
- ● `from_json(cls, d: dict)` @ L126

**types/scores.py** (144 lines)

- `class FiveDimScores` @ L74
- `class ReputationScores` @ L117
- ● `normalize_score_keys(scores: dict)` @ L56
- · `_clamp(value: float, lo: float, hi: float)` @ L69
- · `_fields(self)` @ L91
- ● `average(self)` @ L98
- ● `weighted_average(self, weights: list[float])` @ L103
- ● `to_result(self)` @ L111
- · `_fields(self)` @ L134
- ● `average(self)` @ L137
- ● `to_result(self)` @ L142

**types/status.py** (38 lines)

- ● `is_platform_commit(author_email: str)` @ L20
- ● `parse_status_tag(message: str, author_email: str)` @ L25

### root/

**__main__.py** (27 lines)

- ● `main()` @ L18

**compiler.py** (329 lines)

- `class CompileResult` @ L180
- `class TypstBackend` @ L246
- `class MarkdownBackend` @ L292
- ● `compile_article(source_path: Path, fmt: str | None)` @ L195
- ● `detect_format(file_path: Path)` @ L221
- · `_output_path(source_path: Path, output_dir: Path, ext: str)` @ L233
- · `_typst_format_label(fmt: str)` @ L238
- · `_parse_typst_warnings(stderr: str)` @ L280
- · `_render_markdown(md_text: str)` @ L319
- ● `compile(self, source_path: Path, output_dir: Path, fmt: str)` @ L249
- ● `compile(self, source_path: Path, output_dir: Path)` @ L295

**crypto.py** (236 lines)

- ● `derive_key_pair(password: str, salt_hex: str)` @ L56
- ● `derive_pubkey_hex(password: str, salt_hex: str)` @ L79
- ● `validate_pubkey_hex(pubkey_hex: str)` @ L85
- ● `validate_sig_hex(sig_hex: str)` @ L95
- ● `sha256_hex(data: bytes)` @ L102
- ● `verify_body_hash(body: bytes, claimed_hash: str)` @ L109
- ● `pubkey_hex_to_ssh_line(pubkey_hex: str)` @ L116
- · `_private_key_to_bytes(key: ed25519.Ed25519PrivateKey)` @ L132
- · `_public_key_to_bytes(key: ed25519.Ed25519PublicKey)` @ L137
- ● `load_private_key(key_bytes: bytes)` @ L142
- ● `load_public_key(key_bytes: bytes)` @ L147
- ● `serialize_private_key_pem(private_key_bytes: bytes)` @ L152
- ● `write_key_to_tempfile(private_key_bytes: bytes)` @ L166
- ● `temp_signing_key(private_key_bytes: bytes)` @ L188
- ● `write_allowed_signers_file(email: str, pubkey_ssh_line: str)` @ L206
- ● `new_salt()` @ L218
- ● `sign_detached(private_key_bytes: bytes, message: bytes)` @ L223
- ● `verify_signature(pubkey_bytes: bytes, message: bytes, signature: bytes)` @ L229

**editor.py** (95 lines)

- · `_format_diff_header(diff: str)` @ L35
- ● `get_password(args, confirm: bool)` @ L40
- ● `open_editor(initial: str)` @ L60
- · `_strip_comments(text: str)` @ L76
- ● `prompt_commit_message(diff: str)` @ L82

**exceptions.py** (195 lines)

- `class PeerpediaError` @ L39
- `class NotFoundError` @ L64
- `class NotAuthorizedError` @ L80
- `class ConflictError` @ L97
- `class MergeConflictError` @ L110
- `class AmbiguousError` @ L122
- `class BadRequestError` @ L142
- `class SignatureVerificationError` @ L156
- `class TransportError` @ L170
- `class ProtocolError` @ L184

**frontmatter.py** (70 lines)

- ● `parse_frontmatter(source: str)` @ L19
- ● `make_frontmatter(data: dict)` @ L38
- ● `make_article_frontmatter(title: str, abstract: str | None, keywords: list[str] | None, categories: list[str] | None)` @ L46
- ● `strip_frontmatter(source: str)` @ L63

**messages.py** (397 lines)

- `class Kind` @ L21
- `class Msg` @ L30
- ● `lookup(code: str)` @ L379
- ● `log_text(code: str)` @ L393

**names.py** (72 lines)

- ● `generate_anonymous_name()` @ L10
- ● `derive_anonymous_name(seed: str)` @ L15
- · `_pick_anonymous_name(idx: int)` @ L25

**time.py** (73 lines)

- ● `validate_clock_skew(skew_seconds: int | None)` @ L34
- ● `validate_timestamp(ts_str: str)` @ L49
- ● `compute_clock_skew(server_ts: int, local_ts: int)` @ L67

## 4. CROSS-LAYER DEPENDENCY MATRIX

Rows = importer, Columns = imported. Each cell = number of import statements.

| | app | cli | compiler | compute | config | core | crypto | editor | exceptions | frontmatter | messages | names | presentation | repl | rules | server | storage | time | transport | types |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **app/** | 80 | — | — | — | 7 | 79 | 4 | — | 11 | — | — | — | — | — | 1 | — | 14 | 1 | 3 | 3 |
| **cli/** | 35 | 41 | 1 | — | 8 | 2 | 2 | 4 | 4 | — | 4 | — | 7 | — | — | 1 | — | — | 2 | 2 |
| **compute/** | — | — | — | 1 | 3 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | 6 |
| **config/** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **core/** | — | — | — | 6 | 27 | 133 | 5 | — | 15 | 4 | — | 1 | — | — | 31 | — | 290 | 1 | 2 | 10 |
| **presentation/** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | 1 |
| **repl/** | 15 | — | — | — | 4 | 20 | — | 1 | 2 | — | 1 | — | 7 | 54 | — | — | — | — | — | — |
| **root/** | — | 1 | — | — | 16 | — | — | — | 3 | 1 | — | — | — | 1 | — | — | — | — | — | — |
| **rules/** | — | — | — | — | 1 | — | — | — | 5 | — | — | — | — | — | 13 | — | — | — | — | 5 |
| **server/** | — | — | — | — | 8 | 23 | 1 | — | 13 | — | — | — | — | — | 1 | 17 | 7 | — | 1 | — |
| **storage/** | — | — | — | 3 | 17 | — | 3 | — | 19 | — | — | — | — | — | 1 | — | 153 | — | 1 | 20 |
| **transport/** | — | — | — | — | 2 | — | 6 | — | 9 | — | — | — | — | — | — | — | — | 4 | 47 | — |
| **types/** | — | — | — | — | 1 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

## 5. ARCHITECTURE RULES CHECK

- ✅ PASS — cli/ never imports repl/
- ✅ PASS — repl/ never imports cli/
- ✅ PASS — presentation/ never imports cli/repl/app/core/storage
- ✅ PASS — app/ never imports cli/repl/presentation
- ✅ PASS — repl/ never imports storage/ directly

## 6. POTENTIAL REDUNDANCIES & SMELLS

### Very small files (< 30 lines, few or no functions)
- `__main__.py` — 27 lines, 1 funcs
- `app/__init__.py` — 15 lines, 0 funcs
- `app/commandspec/__init__.py` — 16 lines, 0 funcs
- `cli/cmds/__init__.py` — 26 lines, 0 funcs
- `cli/cmds/mother.py` — 24 lines, 1 funcs
- `cli/cmds/schema.py` — 14 lines, 1 funcs
- `core/articles/_helpers.py` — 18 lines, 1 funcs
- `presentation/__init__.py` — 10 lines, 0 funcs
- `repl/__init__.py` — 21 lines, 0 funcs
- `rules/__init__.py` — 26 lines, 0 funcs
- `server/routes/__init__.py` — 10 lines, 0 funcs

### Commands without handlers (CLI-only, not in REPL)
- `server.start` — NO HANDLER
- `schema` — NO HANDLER
- `compile` — NO HANDLER
- `mother` — NO HANDLER
- `help` — NO HANDLER

### Duplicate public function names across cli/ and repl/
- `display_user` — in `cli/display.py` and `repl/display.py`

### Thin wrappers (delegate to another function with same signature)
These are in `cli/display.py` and `repl/display.py` — they inject `console` then delegate to `presentation/rich/components.py`.
- `_print_table` → `_shared_print_table(console, ...)`
- `_print_panel` → `_shared_print_panel(console, ...)`
- `_status_badge` → `_shared_status_badge(...)`
- `display_user` → `_shared_display_user(console, ...)`
- `_score_lines` → `_shared_score_lines(...)`
- `_stars` → `_shared_score_stars(...)`

### CLI handlers that still use `_article` directly (not spec.handler)
These have significant CLI-specific logic (editor, pager, diff computation):
- `_cmd_article_create` — editor interaction for content
- `_cmd_article_show` — pager for full content
- `_cmd_article_list` — batch author name resolution + Rich rendering
- `_cmd_article_edit` — editor + diff + commit message prompt
- `_cmd_compile` — compilation + file open
## 7. FILE SIZE HEATMAP

### app/ — 2396 lines, 23 files

  app/commandspec/registry.py                             ██████████████████████████████████████████████████████████████████████████████████████████████████████ 306
  app/commands/article.py                                 ████████████████████████████████████████████████████████████████████████████████ 241
  app/commandspec/handlers.py                             █████████████████████████████████████████████████████████████████████████████ 231
  app/commands/social.py                                  ███████████████████████████████████████████████████████████████ 190
  app/commands/sync.py                                    ████████████████████████████████████████████████████ 156
  app/commandspec/schema.py                               ██████████████████████████████████████████████ 140
  app/refs.py                                             ██████████████████████████████████████████████ 140
  app/commands/account.py                                 ████████████████████████████████████████████ 132
  app/commands/review.py                                  ██████████████████████████████████████████ 126
  app/context.py                                          █████████████████████████████████████ 112
  app/commands/bundle.py                                  █████████████████████████████████ 100
  app/parsers.py                                          █████████████████████████████████ 100
  app/commands/maintainer.py                              ███████████████████████ 69
  app/readmodels/articles.py                              ███████████████████████ 69
  app/commandspec/types.py                                ██████████████████████ 68
  app/commands/fork.py                                    █████████████████████ 63
  app/result.py                                           ██████████████ 42
  app/commands/notification.py                            █████████████ 40
  app/commands/dashboard.py                               ██████████ 32
  app/commandspec/__init__.py                             █████ 16
  app/__init__.py                                         █████ 15
  app/commands/__init__.py                                █ 4
  app/readmodels/__init__.py                              █ 4

### cli/ — 2105 lines, 21 files

  cli/parser.py                                           ████████████████████████████████████████████████████████████████████████████████████████████ 277
  cli/info.py                                             ██████████████████████████████████████████████████████████████████████████████████ 246
  cli/cmds/article.py                                     ███████████████████████████████████████████████████████████████████████ 215
  cli/display.py                                          ████████████████████████████████████████████████████████████ 181
  cli/cmds/social.py                                      ████████████████████████████████████████████████ 146
  cli/dispatch.py                                         ████████████████████████████████████████████ 133
  cli/bundle_utils.py                                     ██████████████████████████████████████████ 128
  cli/__init__.py                                         █████████████████████████████████████████ 124
  cli/cmds/account.py                                     ████████████████████████████████ 96
  cli/cmds/reviews.py                                     ████████████████████████████ 85
  cli/decorators.py                                       ███████████████████████████ 83
  cli/session.py                                          ██████████████████████████ 80
  cli/cmds/server.py                                      █████████████████ 53
  cli/cmds/maintainers.py                                 ████████████████ 49
  cli/cmds/fork.py                                        █████████████ 39
  cli/cmds/notifications.py                               ████████████ 38
  cli/cmds/sync.py                                        ███████████ 35
  cli/cmds/help.py                                        ███████████ 33
  cli/cmds/__init__.py                                    ████████ 26
  cli/cmds/mother.py                                      ████████ 24
  cli/cmds/schema.py                                      ████ 14

### repl/ — 1666 lines, 12 files

  repl/browse.py                                          ██████████████████████████████████████████████████████████████████████████████████████ 258
  repl/help.py                                            █████████████████████████████████████████████████████████████████████████████████ 245
  repl/engine.py                                          ████████████████████████████████████████████████████████████████████████ 216
  repl/state.py                                           █████████████████████████████████████████████████████████████ 184
  repl/display.py                                         ██████████████████████████████████████████████ 140
  repl/meta.py                                            ██████████████████████████████████████████████ 139
  repl/dispatch.py                                        ████████████████████████████████████████████ 134
  repl/main.py                                            ████████████████████████████████████████████ 134
  repl/completer.py                                       ████████████████████████ 74
  repl/wizards.py                                         ██████████████████████ 67
  repl/banner.py                                          ██████████████████ 54
  repl/__init__.py                                        ███████ 21

### presentation/ — 126 lines, 3 files

  presentation/rich/components.py                         █████████████████████████████████████ 112
  presentation/__init__.py                                ███ 10
  presentation/rich/__init__.py                           █ 4

### core/ — 2889 lines, 28 files

  core/__init__.py                                        █████████████████████████████████████████████████████████████████ 196
  core/users.py                                           ██████████████████████████████████████████████████████████████ 188
  core/sync_article.py                                    ██████████████████████████████████████████████████████████ 175
  core/reviews/thread.py                                  █████████████████████████████████████████████████████ 159
  core/sync_social.py                                     ███████████████████████████████████████████████████ 154
  core/merge.py                                           ███████████████████████████████████████████████ 143
  core/reviews/invite.py                                  █████████████████████████████████████████████ 136
  core/notifications.py                                   ██████████████████████████████████████████ 127
  core/reconcile/mirror.py                                █████████████████████████████████████████ 123
  core/articles/sink.py                                   ███████████████████████████████████████ 119
  core/guards.py                                          ███████████████████████████████████████ 119
  core/maintainers.py                                     █████████████████████████████████████ 111
  core/articles/update.py                                 ███████████████████████████████████ 107
  core/reviews/submit.py                                  █████████████████████████████████ 100
  core/views.py                                           █████████████████████████████████ 100
  core/articles/publish.py                                ████████████████████████████████ 98
  core/reconcile/score.py                                 ███████████████████████████████ 94
  core/articles/__init__.py                               ████████████████████████████ 85
  core/articles/create.py                                 ████████████████████████████ 84
  core/reviews/__init__.py                                ████████████████████████ 73
  core/articles/rollback.py                               ████████████████████████ 72
  core/articles/diff.py                                   █████████████████████ 65
  core/articles/fork.py                                   ████████████████████ 60
  core/reconcile/__init__.py                              ████████████████████ 60
  core/shares.py                                          ████████████████ 49
  core/articles/delete.py                                 █████████████ 41
  core/bookmarks.py                                       ███████████ 33
  core/articles/_helpers.py                               ██████ 18

### storage/ — 4164 lines, 31 files

  storage/db/crud_user.py                                 ███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 501
  storage/db/crud_article.py                              ██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 474
  storage/db/models.py                                    ███████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 347
  storage/git/read.py                                     █████████████████████████████████████████████████████████████████████████████████████████████████ 292
  storage/peers.py                                        █████████████████████████████████████████████████████████████████ 195
  storage/db/crud_review.py                               ██████████████████████████████████████████████████████████ 174
  storage/db/engine.py                                    ████████████████████████████████████████████████████████ 169
  storage/db/guards.py                                    █████████████████████████████████████████████████████ 160
  storage/git/ops.py                                      ███████████████████████████████████████████████ 142
  storage/git/merge.py                                    ██████████████████████████████████████████████ 139
  storage/locks.py                                        ████████████████████████████████████████ 122
  storage/db/crawler.py                                   ████████████████████████████████████████ 121
  storage/db/ingest.py                                    █████████████████████████████████████ 111
  storage/git/guards.py                                   ██████████████████████████████████ 102
  storage/db/_validators.py                               █████████████████████████████████ 101
  storage/db/crud_notification.py                         ███████████████████████████████ 94
  storage/db/crud_merge.py                                ██████████████████████████████ 92
  storage/db/crud_alias.py                                ███████████████████████████ 83
  storage/db/crud_share.py                                ███████████████████████████ 83
  storage/db/state.py                                     ███████████████████████████ 81
  storage/db/crud_maintainer.py                           █████████████████████████ 76
  storage/git/__init__.py                                 ████████████████████████ 73
  storage/git/bundle.py                                   ███████████████████████ 70
  storage/git/ancestor.py                                 ██████████████████████ 67
  storage/git/trailers.py                                 █████████████████████ 63
  storage/db/crud_citation.py                             ██████████████████ 54
  storage/git/archive.py                                  █████████████████ 52
  storage/db/crud_bookmark.py                             ███████████████ 45
  storage/db/session_utils.py                             ██████████████ 43
  storage/db/__init__.py                                  ███████████ 35
  storage/__init__.py                                     █ 3

### transport/ — 935 lines, 9 files

  transport/http/social.py                                ███████████████████████████████████████████████████████████████████ 203
  transport/http/health.py                                █████████████████████████████████████████████████████████████ 185
  transport/http/articles.py                              ████████████████████████████████████████████████ 145
  transport/http/_core.py                                 █████████████████████████████████████████████ 137
  transport/guards.py                                     ██████████████████████████ 79
  transport/auth.py                                       ███████████████████████ 69
  transport/__init__.py                                   ███████████████████ 59
  transport/http/factory.py                               ██████████████████ 56
  transport/http/__init__.py                              █ 2

### server/ — 881 lines, 11 files

  server/app.py                                           ██████████████████████████████████████████████████████████████ 188
  server/routes/users.py                                  ██████████████████████████████████████████████████████████████ 188
  server/routes/articles.py                               ████████████████████████████████████████████████████████ 168
  server/middleware/auth.py                               ███████████████████████████████ 93
  server/shared.py                                        ███████████████████ 58
  server/middleware/ratelimit.py                          █████████████████ 53
  server/middleware/logging.py                            █████████████ 40
  server/middleware/db.py                                 ████████████ 37
  server/routes/peers.py                                  ████████████ 37
  server/routes/__init__.py                               ███ 10
  server/middleware/__init__.py                           ███ 9

### config/ — 403 lines, 4 files

  config/params.py                                        █████████████████████████████████████████████████████████████████████████████ 233
  config/paths.py                                         ███████████████████████████████ 94
  config/git.py                                           ████████████████████████ 73
  config/__init__.py                                      █ 3

### types/ — 315 lines, 4 files

  types/scores.py                                         ████████████████████████████████████████████████ 144
  types/entities.py                                       ███████████████████████████████████████████ 129
  types/status.py                                         ████████████ 38
  types/__init__.py                                       █ 4

### root/ — 1497 lines, 10 files

  messages.py                                             ████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████ 397
  compiler.py                                             █████████████████████████████████████████████████████████████████████████████████████████████████████████████ 329
  crypto.py                                               ██████████████████████████████████████████████████████████████████████████████ 236
  exceptions.py                                           █████████████████████████████████████████████████████████████████ 195
  editor.py                                               ███████████████████████████████ 95
  time.py                                                 ████████████████████████ 73
  names.py                                                ████████████████████████ 72
  frontmatter.py                                          ███████████████████████ 70
  __main__.py                                             █████████ 27
  __init__.py                                             █ 3
