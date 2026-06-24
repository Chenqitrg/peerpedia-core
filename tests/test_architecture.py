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
        "peerpedia_core/storage/git_backend.py",
        "peerpedia_core/bundle/git_bundle.py",
        "peerpedia_core/transport/http_server.py",  # GitCommandError for error mapping
    }
    for f in _all_modules():
        rel = _rel(f)
        text = f.read_text()
        if ("import git" in text or "from git import" in text) and rel not in _ALLOWED:
            raise AssertionError(f"{rel}: import git forbidden — use git_backend or git_bundle")


def test_no_sqlalchemy_outside_storage_db():
    for f in _all_modules():
        rel = _rel(f)
        if "storage/db/" in rel:
            continue
        text = f.read_text()
        if "import sqlalchemy" in text or "from sqlalchemy" in text:
            raise AssertionError(f"{rel}: sqlalchemy forbidden — use storage/db/ facade or CRUD")


def test_no_internal_peerpedia_imports():
    """Function bodies must not contain ``from peerpedia_core.* import``."""
    # Lazy imports are acceptable for optional heavy dependencies
    # (e.g., starlette/uvicorn in server handlers) to avoid slowing
    # down every CLI command.
    _LAZY_IMPORT_OK = {
        "peerpedia_core/cli/handlers/server.py",  # uvicorn + create_app
    }
    for f in _all_modules():
        rel = _rel(f)
        if rel in _LAZY_IMPORT_OK:
            continue
        for module, name, is_internal in _imports(f):
            if is_internal and module.startswith(_PEERPEDIA):
                raise AssertionError(
                    f"{rel}: internal import from {module} — "
                    "move to module level or move the function"
                )


def test_no_httpx_outside_transport():
    """Only transport/http_client.py and transport/health.py may import httpx."""
    _ALLOWED = {
        "peerpedia_core/transport/http_client.py",
        "peerpedia_core/transport/health.py",
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
_FOUNDATION = {"config/", "policies/", "storage/", "workflow/", "types/",
               "compiler.py", "crypto.py", "exceptions.py", "frontmatter.py", "repl.py"}
# Foundation modules that may import specific network-layer submodules.
_FOUNDATION_MAY_IMPORT_NETWORK: set[str] = set()


def test_foundation_never_imports_network():
    for f in _all_modules():
        rel = _rel(f)
        if not any(rel.startswith(p) for p in _FOUNDATION):
            continue
        for m in _imports_peerpedia_modules(f):
            if any(m.startswith(p) for p in ("peerpedia_core.bundle", "peerpedia_core.social", "peerpedia_core.transport")):
                if m not in _FOUNDATION_MAY_IMPORT_NETWORK:
                    raise AssertionError(
                        f"{rel}: imports {m} — foundation modules must not import network layer (bundle/social/transport)"
                    )


def test_storage_db_and_git_backend_never_import_each_other():
    for f in _all_modules():
        rel = _rel(f)
        if "storage/db/" in rel:
            for m in _imports_peerpedia_modules(f):
                if "git_backend" in m:
                    raise AssertionError(f"{rel}: imports git_backend — db and git_backend are separate")
        if "git_backend.py" in rel:
            for m in _imports_peerpedia_modules(f):
                if "storage.db" in m or "storage/db" in m:
                    raise AssertionError(f"{rel}: imports storage.db — db and git_backend are separate")


def test_policies_only_imports_models_and_exceptions():
    for f in _all_modules():
        rel = _rel(f)
        if "policies/" not in rel:
            continue
        for m in _imports_peerpedia_modules(f):
            if "storage.db.models" not in m and "exceptions" not in m:
                raise AssertionError(
                    f"{rel}: imports {m} — policies may only import models + exceptions"
                )


def test_bundle_client_server_never_import_each_other():
    """bundle_client ↔ bundle_server communicate via HTTP, never by import."""
    _CLIENT = "peerpedia_core/bundle/client.py"
    _SERVER = "peerpedia_core/bundle/server.py"
    for f in _all_modules():
        rel = _rel(f)
        if rel == _CLIENT:
            for m in _imports_peerpedia_modules(f):
                if "bundle_server" in m:
                    raise AssertionError(f"{rel}: imports bundle_server — use HTTP")
        if rel == _SERVER:
            for m in _imports_peerpedia_modules(f):
                if "bundle_client" in m:
                    raise AssertionError(f"{rel}: imports bundle_client — use HTTP")


def test_commands_never_imports_bundle_or_social():
    """Commands submodules must not import bundle/ or social/.  __init__.py facade
    re-exports bundle functions — that's its job, not a violation."""
    for f in _all_modules():
        rel = _rel(f)
        if "commands/" not in rel or "__init__.py" in rel:
            continue
        for m in _imports_peerpedia_modules(f):
            if any(m.startswith(p) for p in ("peerpedia_core.bundle", "peerpedia_core.social", "peerpedia_core.transport")):
                raise AssertionError(
                    f"{rel}: imports {m} — commands submodules must not import network layer"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# C. Leaf modules — zero peerpedia_core imports (or only explicit deps)
# ═══════════════════════════════════════════════════════════════════════════════

# Modules that are leaves NOW and must STAY leaves.
_LEAVES: dict[str, set[str]] = {
    # Pure leaves — zero peerpedia_core imports.
    "bundle/monotonic.py": set(),
    "transport/health.py": set(),
    "exceptions.py": set(),
    "config/paths.py": set(),
    "types/scores.py": set(),
    # Near-leaves — only allowed to import the listed peerpedia modules.
    "bundle/git_bundle.py": {"peerpedia_core.bundle.monotonic"},
    "bundle/pending.py": {"peerpedia_core.config.paths"},
    "storage/locks.py": set(),
    "storage/git_backend.py": {"peerpedia_core.config.paths"},
    "config/params.py": set(),
    "frontmatter.py": set(),
    "compiler.py": set(),
    "crypto.py": set(),
}


def test_leaf_modules_stay_leaves():
    for rel, allowed in _LEAVES.items():
        f = ROOT.parent / rel
        if not f.exists():
            continue
        for m in _imports_peerpedia_modules(f):
            if m not in allowed:
                raise AssertionError(
                    f"{rel}: imports {m} — leaf module, only allowed {allowed or 'nothing'}"
                )


def test_storage_db_only_imports_within_db():
    """storage/db/ files may import each other + SQLAlchemy — nothing else."""
    for f in _all_modules():
        rel = _rel(f)
        if "storage/db/" not in rel:
            continue
        for m in _imports_peerpedia_modules(f):
            if "storage.db" not in m and "storage/db" not in m:
                raise AssertionError(
                    f"{rel}: imports {m} — storage/db/ is a closed layer, "
                    "only import from within storage/db/"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# D. Facade — external code imports from commands.__init__, not submodules
# ═══════════════════════════════════════════════════════════════════════════════

_COMMANDS_SUBMODULES = {
    "peerpedia_core.commands.articles",
    "peerpedia_core.commands.reviews",
    "peerpedia_core.commands.merge",
    "peerpedia_core.commands.bundle",
    "peerpedia_core.commands.users",
    "peerpedia_core.commands.bookmarks",
    "peerpedia_core.commands.workflow",
    "peerpedia_core.commands.maintainers",
}
# Files allowed to import commands submodules directly:
# - commands/__init__.py (the facade itself)
# - commands/* submodules importing each other (internal wiring)
# - tests (setup uses crud directly)

def test_external_code_uses_commands_facade():
    for f in _all_modules():
        rel = _rel(f)
        # Allowed: files inside commands/ or tests/
        if "/commands/" in rel or "/tests/" in rel:
            continue
        for m, _name, _internal in _imports(f):
            if m in _COMMANDS_SUBMODULES:
                raise AssertionError(
                    f"{rel}: imports {m} — use `from peerpedia_core.commands import ...`"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# E. Fail-fast — no error suppression via silent return or bare except
# ═══════════════════════════════════════════════════════════════════════════════

# Modules where ``except Exception: pass`` is explicitly tolerated
# (entry points, HTTP transport, network detection).
_EXCEPT_PASS_ALLOWED = {
    "peerpedia_core/transport/health.py",
    "peerpedia_core/transport/http_client.py",
    "peerpedia_core/cli/helpers.py",  # _with_db: logs traceback before die
    "peerpedia_core/storage/db/session_utils.py",  # rollback on exit
    "peerpedia_core/cli/bundle_utils.py",  # sync fallback
}

# HTTP transport returns None on network failure — caller retries.
_EXCEPT_RETURN_NONE_ALLOWED = {
    "peerpedia_core/transport/http_client.py",
    "peerpedia_core/transport/health.py",
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
# F. Tests are immutable — AI agents must not rewrite them
# ═══════════════════════════════════════════════════════════════════════════════

def test_architecture_rules_are_immutable():
    """test_architecture.py is the constitution — it must be read-only.
    To amend architecture rules: chmod +w, edit, chmod 444."""
    import os
    import stat

    f = Path(__file__)
    mode = f.stat().st_mode
    writable = mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    if writable:
        raise AssertionError(
            "tests/test_architecture.py is writable — "
            "architecture rules are the constitution and must be read-only. "
            "Run: chmod 444 tests/test_architecture.py"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# G. git_bundle boundary — who may import git_bundle
# ═══════════════════════════════════════════════════════════════════════════════

_GIT_BUNDLE_IMPORT_ALLOWED = {
    "peerpedia_core/bundle/client.py",
    "peerpedia_core/bundle/server.py",
    "peerpedia_core/bundle/__init__.py",
    "peerpedia_core/bundle/git_bundle.py",  # self-import for type annotations
}


def test_only_sync_layer_imports_git_bundle():
    """Only bundle/client, bundle/server, and bundle/__init__ may import git_bundle."""
    for f in _all_modules():
        rel = _rel(f)
        if rel in _GIT_BUNDLE_IMPORT_ALLOWED:
            continue
        for m, _name, _internal in _imports(f):
            if m == "peerpedia_core.bundle.git_bundle":
                raise AssertionError(
                    f"{rel}: imports peerpedia_core.bundle.git_bundle — "
                    "git_bundle is the pure protocol layer; use bundle/ facade or client/server instead"
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
    "peerpedia_core/commands/",
    "peerpedia_core/storage/db/",
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
