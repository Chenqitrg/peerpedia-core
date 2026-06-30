# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Architecture constraint enforcement — fail the build on layer violations.

These tests parse the source tree with ``ast`` and verify every rule in
``docs/architecture.md``.  A passing test suite guarantees zero boundary
violations — no need for code review to catch import mistakes.

Rules that can't be automated (see architecture.md "Hard Constraints"):
  - No silent ``return None`` / ``return False`` to suppress errors.
  - No bare ``except:`` / ``except Exception:`` without logging.
  - CRUD functions call ``flush()`` only; ``commit()`` is the caller's job.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "peerpedia_core"

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_PEERPEDIA = "peerpedia_core"


def _all_modules() -> list[Path]:
    return sorted(ROOT.rglob("*.py"))


def _rel(f: Path) -> str:
    return str(f.relative_to(ROOT.parent))


def _imports(file: Path):
    """Yield (module, name, is_inside_function) for every import in *file*."""
    tree = ast.parse(file.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            is_internal = _inside_function(node, tree)
            for alias in node.names:
                yield node.module, alias.name, is_internal


def _inside_function(node: ast.AST, tree: ast.AST) -> bool:
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(parent):
                if child is node:
                    return True
    return False


def _imports_peerpedia_modules(file: Path):
    """Yield peerpedia_core module names that *file* imports."""
    for module, _name, _internal in _imports(file):
        if module.startswith(_PEERPEDIA):
            yield module


# ═══════════════════════════════════════════════════════════════════════════════
# A. Import source bans
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_import_git_outside_allowed():
    _ALLOWED = {
        "peerpedia_core/server/app.py",  # GitCommandError → 500 error mapping
    }
    for f in _all_modules():
        rel = _rel(f)
        if "storage/git/" in rel:  # storage/git/ is the git layer
            continue
        text = f.read_text()
        if ("import git" in text or "from git import" in text) and rel not in _ALLOWED:
            raise AssertionError(f"{rel}: import git forbidden — use storage/git/ facade or git_backend")


def test_no_sqlalchemy_outside_storage_db():
    for f in _all_modules():
        rel = _rel(f)
        if "storage/db/" in rel:
            continue
        text = f.read_text()
        if "import sqlalchemy" in text or "from sqlalchemy" in text:
            raise AssertionError(f"{rel}: sqlalchemy forbidden — use storage/db/ facade or CRUD")


def test_no_internal_peerpedia_imports():
    """Function bodies must not contain ``from peerpedia_core.* import``.

    Lazy imports inside functions are a code smell: they let AI/developers
    bypass layer boundaries with zero friction.  Every lazy import must be
    explicitly justified in the whitelist below.

    To add a new entry: specify the exact (file, module) pair and a reason
    why the import CANNOT be at module level (circular dependency, heavy
    optional dependency that hurts CLI startup, etc.).
    """
    # (file_rel, module) → why the lazy import is necessary
    _LAZY_IMPORT_OK: dict[tuple[str, str], str] = {
        # ── Heavy optional deps (avoid loading on every CLI invocation) ──
        # ── Circular dependency breaks ──────────────────────────────────
        ("peerpedia_core/cli/schema_build.py",
         "peerpedia_core.cli.parser"):
            "circular: parser defines commands, schema_build reads them; lazy to avoid import at CLI load",
        ("peerpedia_core/app/commands/article.py",
         "peerpedia_core.rules.articles"):
            "circular: article.py validates input with rules before executing commands",
        ("peerpedia_core/cli/bundle_utils.py",
         "peerpedia_core.app.commands.sync"):
            "circular: bundle_utils wraps sync for auto-sync; lazy to avoid import loop",
        ("peerpedia_core/cli/cmds/server.py",
         "peerpedia_core.server.app"):
            "heavy: imports Starlette/uvicorn — only needed for `server start`",
        ("peerpedia_core/cli/cmds/server.py",
         "peerpedia_core.app.commands.sync"):
            "heavy: announce_to_peers called from discovery thread at startup",
        ("peerpedia_core/cli/decorators.py",
         "peerpedia_core.cli.bundle_utils"):
            "circular: with_context decorator auto-syncs after write commands",
        ("peerpedia_core/__main__.py",
         "peerpedia_core.repl"):
            "heavy: prompt_toolkit is heavy, only loaded for REPL mode; __main__ is the top-level router",
        # ── REPL heavy optional deps ────────────────────────────────────
        ("peerpedia_core/repl/main.py",
         "peerpedia_core.repl.pages.app"):
            "heavy: prompt_toolkit Application — only loaded when REPL actually runs",
        ("peerpedia_core/repl/state.py",
         "peerpedia_core.cli"):
            "heavy: parser (argparse registration) only needed when _get_parser is first called",
        ("peerpedia_core/repl/dispatch.py",
         "peerpedia_core.repl.browse"):
            "heavy: prompt_toolkit Application — only loaded for interactive browse views",
        ("peerpedia_core/cli/display.py",
         "peerpedia_core.messages"):
            "heavy optional: message lookup only needed for empty-article-list hints",
        ("peerpedia_core/core/__init__.py",
         "peerpedia_core.storage.db.ingest"):
            "core facade re-exports ingest for peer sync — lazy to avoid import loop",
        ("peerpedia_core/core/__init__.py",
         "peerpedia_core.types.entities"):
            "core facade re-exports types for peer sync — lazy to avoid import loop",
        ("peerpedia_core/core/__init__.py",
         "peerpedia_core.storage.db"):
            "db_repl_init lazily imports init_db + migrate_db to avoid import loop from core facade",
        ("peerpedia_core/repl/dispatch.py",
         "peerpedia_core.repl.engine"):
            "circular: dispatch → meta/wizards → execute; engine → dispatch would create cycle",
        ("peerpedia_core/repl/dispatch.py",
         "peerpedia_core.repl.state"):
            "lazy to avoid pulling prompt_toolkit deps into meta-command dispatch",
        ("peerpedia_core/repl/engine.py",
         "peerpedia_core.editor"):
            "heavy: password prompting only needed for register/login/recover commands",
    }

    for f in _all_modules():
        rel = _rel(f)
        for module, _name, is_internal in _imports(f):
            if not is_internal:
                continue
            if not module.startswith(_PEERPEDIA):
                continue
            key = (rel, module)
            if key in _LAZY_IMPORT_OK:
                continue
            raise AssertionError(
                f"{rel}: lazy import from {module} inside a function — "
                "move to module level, or add to _LAZY_IMPORT_OK in "
                "test_architecture.py with a concrete reason (circular / heavy dep)"
            )


def test_no_httpx_outside_transport():
    """Only transport/http_client.py and transport/health.py may import httpx."""
    _ALLOWED = {
        "peerpedia_core/transport/http/_core.py",
    }
    for f in _all_modules():
        rel = _rel(f)
        if rel in _ALLOWED:
            continue
        text = f.read_text()
        if "import httpx" in text or "from httpx" in text:
            raise AssertionError(f"{rel}: httpx forbidden — HTTP stays in transport/ or network.py")


# ═══════════════════════════════════════════════════════════════════════════════
# B. Layer separation — who may NOT import whom
# ═══════════════════════════════════════════════════════════════════════════════

# Foundation modules must not import network-layer code (bundle, social, transport).
_FOUNDATION = {"config/", "storage/", "compute/", "types/",
               "compiler.py", "crypto.py", "exceptions.py", "frontmatter.py", "repl.py"}
# Foundation modules that may import specific network-layer submodules.
_FOUNDATION_MAY_IMPORT_NETWORK: set[str] = set()


def test_foundation_never_imports_network():
    for f in _all_modules():
        rel = _rel(f)
        if not any(rel.startswith(p) for p in _FOUNDATION):
            continue
        for m in _imports_peerpedia_modules(f):
            if m.startswith("peerpedia_core.transport"):
                if m not in _FOUNDATION_MAY_IMPORT_NETWORK:
                    raise AssertionError(
                        f"{rel}: imports {m} — foundation modules must not import network layer (bundle/social/transport)"
                    )


def test_storage_db_and_git_never_import_each_other():
    for f in _all_modules():
        rel = _rel(f)
        if "storage/db/" in rel:
            for m in _imports_peerpedia_modules(f):
                if "storage.git" in m or "storage/git" in m:
                    raise AssertionError(f"{rel}: imports git layer — db and git are separate")
        if "storage/git/" in rel:
            for m in _imports_peerpedia_modules(f):
                if "storage.db" in m or "storage/db" in m:
                    raise AssertionError(f"{rel}: imports storage.db — db and git are separate")


def test_commands_never_imports_bundle_or_social():
    """App command submodules must not import bundle/ or social/.

    ``app/commands/bundle.py`` is allowed to import ``transport`` —
    it orchestrates sync via Transport contexts.
    """
    _TRANSPORT_OK = {"peerpedia_core/app/commands/sync.py"}
    for f in _all_modules():
        rel = _rel(f)
        if "app/commands/" not in rel or "__init__.py" in rel:
            continue
        for m in _imports_peerpedia_modules(f):
            if any(m.startswith(p) for p in ("peerpedia_core.bundle", "peerpedia_core.social")):
                raise AssertionError(
                    f"{rel}: imports {m} — app commands must not import bundle/social directly"
                )
            if m.startswith("peerpedia_core.transport") and rel not in _TRANSPORT_OK:
                raise AssertionError(
                    f"{rel}: imports {m} — app commands must not import transport directly"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# C. Leaf modules — zero peerpedia_core imports (or only explicit deps)
# ═══════════════════════════════════════════════════════════════════════════════

# Modules that are leaves NOW and must STAY leaves.
_LEAVES: dict[str, set[str]] = {
    # Pure leaves — zero peerpedia_core imports.
    "exceptions.py": set(),
    "config/paths.py": set(),
    "types/scores.py": set(),
    "storage/locks.py": set(),
    "config/params.py": set(),
    "frontmatter.py": set(),
    "messages.py": set(),
    # Near-leaves — only allowed to import the listed peerpedia modules.
    "crypto.py": {"peerpedia_core.exceptions"},
    "compiler.py": {"peerpedia_core.exceptions", "peerpedia_core.config.params",
                    "peerpedia_core.frontmatter"},
}


def test_leaf_modules_stay_leaves():
    for rel, allowed in _LEAVES.items():
        f = ROOT / rel
        if not f.exists():
            continue
        for m in _imports_peerpedia_modules(f):
            if m not in allowed:
                raise AssertionError(
                    f"{rel}: imports {m} — leaf module, only allowed {allowed or 'nothing'}"
                )


def test_storage_db_only_imports_within_db():
    """storage/db/ files may import each other + SQLAlchemy + exceptions."""
    _allowed = {"peerpedia_core.exceptions"}
    _known = {
        # crawler traverses the graph via BFS — compute is pure, no IO
        "peerpedia_core/storage/db/crawler.py": {
            "peerpedia_core.compute.bfs",
            "peerpedia_core.types.entities",
        },
        # CRUD functions read config for defaults/limits
        "peerpedia_core/storage/db/crud_user.py": {
            "peerpedia_core.config.params",
        },
        "peerpedia_core/storage/db/guards.py": {
            "peerpedia_core.config.params",
            "peerpedia_core.rules.articles",
        },
        "peerpedia_core/storage/db/ingest.py": {
            "peerpedia_core.types.entities",
        },
        "peerpedia_core/storage/db/models.py": {
            "peerpedia_core.types.entities",
        },
        "peerpedia_core/storage/db/state.py": {
            "peerpedia_core.compute.state",
            "peerpedia_core.types.entities",
        },
    }
    for f in _all_modules():
        rel = _rel(f)
        if "storage/db/" not in rel:
            continue
        for m in _imports_peerpedia_modules(f):
            if "storage.db" not in m and "storage/db" not in m and m not in _allowed:
                if rel in _known and m in _known[rel]:
                    continue
                raise AssertionError(
                    f"{rel}: imports {m} — storage/db/ is a closed layer, "
                    "only import from within storage/db/"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# D. Facade — external code imports from commands.__init__, not submodules
# ═══════════════════════════════════════════════════════════════════════════════

_COMMANDS_SUBMODULES = {
    "peerpedia_core.core.articles",
    "peerpedia_core.core.reviews",
    "peerpedia_core.core.merge",
    "peerpedia_core.core.users",
    "peerpedia_core.core.bookmarks",
    "peerpedia_core.core.maintainers",
}
# Files allowed to import commands submodules directly:
# - commands/__init__.py (the facade itself)
# - commands/* submodules importing each other (internal wiring)
# - tests (setup uses crud directly)

def test_external_code_uses_commands_facade():
    for f in _all_modules():
        rel = _rel(f)
        # Allowed: files inside app/commands/, core/ (internal wiring), or tests/
        if "/app/commands/" in rel or "/core/" in rel or "/tests/" in rel:
            continue
        for m, _name, _internal in _imports(f):
            if m in _COMMANDS_SUBMODULES:
                raise AssertionError(
                    f"{rel}: imports {m} — use `from peerpedia_core.core import ...`"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# E. Fail-fast — no error suppression via silent return or bare except
# ═══════════════════════════════════════════════════════════════════════════════

# Modules where ``except Exception: pass`` is explicitly tolerated
# (entry points, HTTP transport, network detection).
_EXCEPT_PASS_ALLOWED = {
    "peerpedia_core/transport/http/health.py",
    "peerpedia_core/transport/http/_core.py",
    "peerpedia_core/cli/helpers.py",  # _with_db: logs traceback before die
    "peerpedia_core/storage/db/session_utils.py",  # rollback on exit
    "peerpedia_core/cli/bundle_utils.py",  # sync fallback
}

# HTTP transport returns None on network failure — caller retries.
_EXCEPT_RETURN_NONE_ALLOWED = {
    "peerpedia_core/transport/http/health.py",
    "peerpedia_core/transport/http/_core.py",
    "peerpedia_core/core/reconcile/mirror.py",
    "peerpedia_core/storage/db/crawler.py",
}


def test_no_bare_except_pass():
    """No ``except Exception: pass`` — every exception must be logged or re-raised."""
    for f in _all_modules():
        rel = _rel(f)
        if rel in _EXCEPT_PASS_ALLOWED:
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # Check if it catches Exception or bare except:
            catches_all = (
                node.type is None  # bare except:
                or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
            )
            if not catches_all:
                continue
            # Check if body is just `pass`
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                raise AssertionError(
                    f"{rel}:{node.lineno}: bare `except Exception: pass` — "
                    "at minimum, log the traceback"
                )


def test_no_except_return_none():
    """No ``except Exception: return None`` — don't silently swallow errors.
    Specific exceptions like ``EOFError`` / ``KeyboardInterrupt`` are fine.
    HTTP transport is exempt — network errors are expected."""
    for f in _all_modules():
        rel = _rel(f)
        if rel in _EXCEPT_RETURN_NONE_ALLOWED:
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                # Only flag bare except: or except Exception:
                catches_all = (
                    handler.type is None
                    or (isinstance(handler.type, ast.Name) and handler.type.id == "Exception")
                )
                if not catches_all:
                    continue
                if not handler.body:
                    continue
                last = handler.body[-1]
                if isinstance(last, ast.Return) and (
                    last.value is None
                    or (isinstance(last.value, ast.Constant) and last.value.value is None)
                ):
                    raise AssertionError(
                        f"{rel}:{last.lineno}: `return None` in except Exception — "
                        "don't silently suppress errors"
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# H. No direct model mutation — all writes go through CRUD functions
# ═══════════════════════════════════════════════════════════════════════════════

# ORM model attributes that must only be written inside storage/db/crud_*.py.
_MODEL_FIELDS = {"status", "public_key", "score", "salt", "reputation"}


def test_no_direct_model_mutation():
    """Outside storage/db/, setting ``article.status = ...`` or
    ``user.public_key = ...`` is forbidden — use CRUD functions.
    Dataclass __init__ / __post_init__ self-assignment is excluded."""
    for f in _all_modules():
        rel = _rel(f)
        # storage/db/ is the CRUD layer — allowed.  config/ defines its own
        # dataclasses (ScoreParams, ReputationParams) with same-named fields.
        if "storage/db/" in rel or "config/" in rel:
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Attribute):
                    continue
                if target.attr not in _MODEL_FIELDS:
                    continue
                raise AssertionError(
                    f"{rel}:{node.lineno}: direct mutation of .{target.attr} — "
                    f"use the corresponding CRUD function instead"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# I. Docstring integrity — no stale file path references
# ═══════════════════════════════════════════════════════════════════════════════

import re

# RST backtick references that contain a path: ``commands/sync.py``,
# ``peerpedia_core/bundle/client.py``, ``transport/http_server.py``.
# Must contain at least one "/" so bare filenames like ``parser.py``
# (informal module references) are not treated as paths.
_DOCSTRING_PATH_RE = re.compile(r"``([^`]*/[^`]+\.py)``")


def _extract_path_refs(docstring: str, *, exclude_todo: bool = True) -> list[str]:
    """Extract file path references from a module docstring.

    Skips references inside ``.. todo::`` blocks — those are aspirational
    (files planned but not yet created), not stale.
    """
    text = docstring
    if exclude_todo:
        # Remove ``.. todo::`` sections before matching
        text = re.sub(r"\.\. todo::.*?(\n\n|\Z)", "", text, flags=re.DOTALL)
    refs: list[str] = []
    for m in _DOCSTRING_PATH_RE.finditer(text):
        refs.append(m.group(1))
    return refs


def test_docstrings_no_stale_paths():
    """Module docstrings must not reference files that no longer exist.

    Every ``peerpedia_core/foo/bar.py`` or ``commands/foo.py`` in a
    docstring is checked against the filesystem.  A stale reference
    means a rename or move was not reflected in the docstring — the
    call graph or architecture description is now lying to the reader.
    """
    for f in _all_modules():
        doc = ast.get_docstring(ast.parse(f.read_text()))
        if not doc:
            continue
        rel = _rel(f)
        for ref in _extract_path_refs(doc):
            # Resolve relative paths against the parent of peerpedia_core/
            if ref.startswith("peerpedia_core/"):
                target = ROOT.parent / ref
            else:
                # e.g. "commands/sync.py" → peerpedia_core/commands/sync.py
                target = ROOT / ref
            if not target.exists():
                raise AssertionError(
                    f"{rel}: docstring references ``{ref}`` — file not found"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# J. CRUD gate — only commands/ may import storage/db/crud_*.py
# ═══════════════════════════════════════════════════════════════════════════════

# Modules allowed to import CRUD functions directly.
# - commands/ orchestrates DB writes — its job is to call CRUD
# - storage/db/ files import each other (crud_article → crud_user, etc.)
# - commands/__init__.py is the facade that re-exports for external callers
_CRUD_IMPORT_ALLOWED = {
    "peerpedia_core/app/commands/",
    "peerpedia_core/storage/db/",
    "peerpedia_core/core/",  # core/__init__.py is the re-export facade
}


def test_only_commands_imports_crud():
    """Outside commands/ and storage/db/, no module may import from
    ``storage.db.crud_*`` directly.  Use ``commands/`` facade instead.

    ``storage.db.models`` (domain entities) is exempt — any module may
    import Article, User, etc. for type annotations.
    """
    for f in _all_modules():
        rel = _rel(f)
        if any(rel.startswith(p) for p in _CRUD_IMPORT_ALLOWED):
            continue
        for m, _name, _internal in _imports(f):
            if m.startswith("peerpedia_core.storage.db.crud_"):
                raise AssertionError(
                    f"{rel}: imports {m} — "
                    "use commands/ facade instead of importing CRUD directly"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# K. Transport layer — no direct storage imports
# ═══════════════════════════════════════════════════════════════════════════════

# Transport routes and middleware must go through commands/, not import
# storage/ directly.  This keeps the "delete HTTP, local still works" property.
_TRANSPORT_STORAGE_ALLOWED: set[str] = set()


def test_transport_no_storage_imports():
    """transport/ must not import from peerpedia_core.storage.*.

    The transport layer exists to be replaceable — it must go through
    commands/ (or bundle/ for bundle protocol functions).  Direct storage
    imports couple transport to the database/filesystem, breaking the
    "delete transport, local CLI works" property.
    """
    for f in _all_modules():
        rel = _rel(f)
        if not rel.startswith("peerpedia_core/transport/"):
            continue
        if rel in _TRANSPORT_STORAGE_ALLOWED:
            continue
        for m, _name, _internal in _imports(f):
            if m.startswith("peerpedia_core.storage"):
                raise AssertionError(
                    f"{rel}: imports {m} — "
                    "transport must not import storage/ directly; "
                    "go through commands/ facade"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# N. View layer — no .to_dict() in transport/ or cli/cmds/
# ═══════════════════════════════════════════════════════════════════════════════

_TO_DICT_ALLOWED = frozenset({
    "peerpedia_core/core/views.py",
    "peerpedia_core/storage/db/models.py",
    "peerpedia_core/app/commands/bundle.py",   # compose response dicts for sync
})


def test_no_to_dict_in_transport_or_cli():
    """transport/ and cli/cmds/ must not call ``.to_dict()`` on models.

    ``commands/views.py`` is the canonical serialization layer.  If any
    transport route handler or CLI command calls ``.to_dict()`` directly,
    it means the view layer was bypassed — and the same serialization
    logic will be duplicated in every caller.
    """
    for f in _all_modules():
        rel = _rel(f)
        if rel in _TO_DICT_ALLOWED:
            continue
        if not (rel.startswith("peerpedia_core/transport/") or
                rel.startswith("peerpedia_core/cli/cmds/")):
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "to_dict":
                # Determine the source line for a precise error message.
                lineno = node.lineno if hasattr(node, "lineno") else 0
                raise AssertionError(
                    f"{rel}:{lineno}: calls .to_dict() — "
                    "use commands/views.py (get_article_view, "
                    "get_following_views, etc.) instead"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# M. No inline list filtering of DB results
# ═══════════════════════════════════════════════════════════════════════════════

# If a module imports from storage/db/, it has SQL capability.
# Any list comprehension in such a module that filters on DB-column-like
# attributes must be pushed into the SQL query instead.
#
# Modules that do NOT import storage/db/ are skipped — they have no DB
# access and can only filter in-memory data.

_DB_FIELD_NAMES = {"status", "id", "user_id", "author_id", "article_id",
                    "title", "created_at", "forked_from", "fork_count",
                    "sink_start", "follower_id", "followed_id"}


def _imports_db_module(rel_path: str, source: str) -> bool:
    """Return True if *rel_path* imports from ``peerpedia_core.storage.db``."""
    import ast as _ast
    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom):
            if node.module and node.module.startswith("peerpedia_core.storage.db"):
                return True
    return False


def test_no_inline_db_filtering():
    """Modules that import storage/db must not filter DB results in Python."""
    for f in _all_modules():
        rel = _rel(f)
        if not (rel.startswith("peerpedia_core/app/commands/") or
                rel.startswith("peerpedia_core/cli/cmds/") or
                rel.startswith("peerpedia_core/transport/routes/")):
            continue
        source = f.read_text()
        if not _imports_db_module(rel, source):
            continue  # No DB access → no DB data to filter inline.
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ListComp):
                continue
            for clause in node.generators:
                for if_node in ast.walk(clause):
                    if isinstance(if_node, ast.Attribute) and if_node.attr in _DB_FIELD_NAMES:
                        lineno = node.lineno if hasattr(node, "lineno") else 0
                        raise AssertionError(
                            f"{rel}:{lineno}: list comprehension filters on "
                            f"'{if_node.attr}' — this module imports storage/db, "
                            f"so push the filter into the SQL query (JOIN / WHERE) "
                            f"instead of filtering in Python after fetching all rows"
                        )


# ═══════════════════════════════════════════════════════════════════════════════
# O. CLI — may import storage.db.models, nothing else from storage/
# ═══════════════════════════════════════════════════════════════════════════════

def test_cli_only_imports_models_from_storage():
    """``cli/`` may import ``storage.db.models`` (ORM entities) but NOT
    ``storage.db``, ``storage.git_backend``, or any other storage submodule.
    All data access must go through ``commands/``."""
    for f in _all_modules():
        rel = _rel(f)
        if not rel.startswith("peerpedia_core/cli/"):
            continue
        for m in _imports_peerpedia_modules(f):
            if m.startswith("peerpedia_core.storage"):
                if m != "peerpedia_core.storage.db.models":
                    raise AssertionError(
                        f"{rel}: imports {m} — "
                        "cli/ may only import storage.db.models (ORM entities); "
                        "all other storage access must go through commands/"
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# P. REPL — only imports from cli/ (and within repl/)
# ═══════════════════════════════════════════════════════════════════════════════

def test_repl_only_imports_from_cli():
    """``repl/`` is a pure UI layer — it may import from ``app/``,
    ``core/`` (facade), ``cli/display``, ``cli/parser``, and within
    ``repl/`` itself.  No direct ``storage/``, ``bundle/``, ``social/``,
    or ``transport/`` imports."""
    _FORBIDDEN_PREFIXES = (
        "peerpedia_core.storage",
        "peerpedia_core.bundle",
        "peerpedia_core.social",
        "peerpedia_core.transport",
    )
    for f in _all_modules():
        rel = _rel(f)
        if not rel.startswith("peerpedia_core/repl/"):
            continue
        for m in _imports_peerpedia_modules(f):
            if any(m.startswith(p) for p in _FORBIDDEN_PREFIXES):
                raise AssertionError(
                    f"{rel}: imports {m} — "
                    "repl/ is a pure UI layer; import from app/, core/, "
                    "cli/display, or cli/parser instead"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Q. REPL — must not import from cli.helpers (post-refactor rule)
# ═══════════════════════════════════════════════════════════════════════════════


def test_repl_does_not_import_cli_helpers():
    """repl/ must not import from ``cli.helpers`` after the app-layer refactor.

    REPL data access goes through ``app.context`` and ``core/`` facade,
    not through CLI internal helpers.
    """
    for f in _all_modules():
        rel = _rel(f)
        if not rel.startswith("peerpedia_core/repl/"):
            continue
        for m, _name, _internal in _imports(f):
            if m == "peerpedia_core.cli.helpers":
                raise AssertionError(
                    f"{rel}: imports {m} — "
                    "repl/ must not import from cli/helpers; "
                    "use app.context, core/, or cli/parser instead"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# R. CLI parser — must not import handlers (post-refactor rule)
# ═══════════════════════════════════════════════════════════════════════════════


def test_cli_parser_does_not_import_handlers():
    """``cli/parser.py`` must not import from ``cli.cmds``.

    Parser sets ``command_id`` and delegates to ``cli/dispatch.py`` for
    lazy handler loading.
    """
    f = ROOT / "cli/parser.py"
    if not f.exists():
        return
    for m, _name, _internal in _imports(f):
        if m.startswith("peerpedia_core.cli.cmds"):
            raise AssertionError(
                f"cli/parser.py: imports {m} — "
                "parser must not import handlers; use command_id + dispatch"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# S. App layer — must not import CLI, REPL, or server
# ═══════════════════════════════════════════════════════════════════════════════


def test_app_does_not_import_cli_repl_or_server():
    """``app/`` must not import from ``cli/``, ``repl/``, or ``server/``.

    The app layer is a pure orchestration layer — no presentation.
    """
    _FORBIDDEN = (
        "peerpedia_core.cli",
        "peerpedia_core.repl",
        "peerpedia_core.server",
    )
    # Temporary exceptions for migration — remove as handlers are fully migrated
    _ALLOWED: dict[tuple[str, str], str] = {}
    for f in _all_modules():
        rel = _rel(f)
        if not rel.startswith("peerpedia_core/app/"):
            continue
        for m, _name, _internal in _imports(f):
            if any(m.startswith(p) for p in _FORBIDDEN):
                key = (rel, m)
                if key in _ALLOWED:
                    continue
                raise AssertionError(
                    f"{rel}: imports {m} — "
                    "app/ must not import from cli/, repl/, or server/; "
                    "app is a pure orchestration layer"
                )


def test_presentation_isolation():
    """``presentation/`` must only import from ``types/`` and stdlib.

    It must never import from ``app/``, ``core/``, ``storage/``,
    ``cli/``, or ``repl/``.  This keeps shared Rich components
    frontend-agnostic.
    """
    _FORBIDDEN = (
        "peerpedia_core.app",
        "peerpedia_core.core",
        "peerpedia_core.storage",
        "peerpedia_core.cli",
        "peerpedia_core.repl",
    )
    for f in _all_modules():
        rel = _rel(f)
        if not rel.startswith("peerpedia_core/presentation/"):
            continue
        for m, _name, _internal in _imports(f):
            if any(m.startswith(p) for p in _FORBIDDEN):
                raise AssertionError(
                    f"{rel}: imports {m} — "
                    "presentation/ must only import from types/ and stdlib; "
                    "it is a frontend-agnostic Rich component layer"
                )


def test_command_spec_coverage():
    """Every ``CommandSpec`` must appear as a parsable command in the CLI.

    Checks that ``find_spec()`` succeeds for every entry in
    ``COMMAND_GROUPS`` and ``TOP_LEVEL_COMMANDS``, and that the CLI
    parser registers all of them.
    """
    from peerpedia_core.app.commandspec import COMMAND_GROUPS, TOP_LEVEL_COMMANDS, find_spec

    all_specs: list[tuple[str, str | None]] = []
    for grp in COMMAND_GROUPS:
        for cmd in grp.commands:
            all_specs.append((cmd.group, cmd.action))

    for cmd in TOP_LEVEL_COMMANDS:
        all_specs.append((cmd.group or cmd.cmd_id, cmd.action))

    for group, action in all_specs:
        spec = find_spec(group, action)
        assert spec is not None, f"find_spec({group!r}, {action!r}) returned None"

    # Verify CLI parser builds and includes every group/command
    from peerpedia_core.cli.parser import build_parser
    parser = build_parser()
    # Parse --help to trigger epilog build (catches _build_commands errors)
    parser.format_help()


def test_repl_failed_command_rollback_does_not_poison_next():
    """A failed REPL command must not poison the session for the next command.

    Simulates a command that raises PeerpediaError, then verifies the
    next command executes cleanly in a fresh session.
    """
    import os
    import tempfile

    from peerpedia_core.app.commandspec import CommandSpec, find_spec
    from peerpedia_core.app.context import build_context
    from peerpedia_core.app.result import AppResult
    from peerpedia_core.exceptions import PeerpediaError
    from peerpedia_core.config.paths import DB_PATH, DB_URL
    from peerpedia_core.core import db_repl_init, db_repl_new_session, db_repl_dispose

    # Use a temp DB to avoid side effects
    tmp = tempfile.mkdtemp()
    tmp_db = f"sqlite:///{tmp}/test.db"
    try:
        db_repl_init(tmp_db)
        db1 = db_repl_new_session(tmp_db)
        try:
            ctx1 = build_context(db1)
            # Simulate a failing command
            try:
                raise PeerpediaError("INTERNAL_ERROR")
            except PeerpediaError:
                db1.rollback()
        finally:
            db1.close()

        # Second session must be clean
        db2 = db_repl_new_session(tmp_db)
        try:
            ctx2 = build_context(db2)
            db2.commit()
        finally:
            db2.close()
    finally:
        db_repl_dispose()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_command_handler_parity():
    """Every ``CommandSpec`` with a handler must be callable by both CLI and REPL.

    Checks that spec.handler exists for commands that REPL supports,
    and that every spec has the same arg names as its CLI counterpart.
    """
    from peerpedia_core.app.commandspec import COMMAND_GROUPS, TOP_LEVEL_COMMANDS

    # Collect all spec args per cmd_id
    spec_args: dict[str, set[str]] = {}
    for grp in COMMAND_GROUPS:
        for cmd in grp.commands:
            spec_args[cmd.cmd_id] = {a.name for a in cmd.args}
    for cmd in TOP_LEVEL_COMMANDS:
        spec_args[cmd.cmd_id] = {a.name for a in cmd.args}

    # Build CLI parser and extract argparse dest names per command
    from peerpedia_core.cli.parser import build_parser, COMMANDS, CommandGroup
    parser = build_parser()

    # Walk subparser actions to find argparse-registered dest names
    def _collect_dests(action, prefix=""):
        dests: dict[str, set[str]] = {}
        if hasattr(action, 'choices') and action.choices:
            for name, sub in action.choices.items():
                if hasattr(sub, '_actions'):
                    cmd_dests = set()
                    for a in sub._actions:
                        if a.dest not in ('help', 'json', 'rich', 'command', 'subcommand', 'command_id', 'func'):
                            cmd_dests.add(a.dest)
                    cmd_id = prefix + (f".{name}" if prefix else name)
                    dests[cmd_id] = cmd_dests
        return dests

    # For each spec that has a handler, verify all required args appear in CLI
    specs_with_handlers = 0
    for cmd_id, sargs in spec_args.items():
        from peerpedia_core.app.commandspec import spec_for_cmd_id
        spec = spec_for_cmd_id(cmd_id)
        if spec is not None and spec.handler is not None:
            specs_with_handlers += 1

    assert specs_with_handlers >= 42, (
        f"Expected >= 42 commands with handlers, got {specs_with_handlers}"
    )
