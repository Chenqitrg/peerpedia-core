# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Documentation integrity enforcement — fail the build on missing docstrings.

These tests parse the source tree with ``ast`` and verify:

1. Every ``.py`` file has a module-level docstring.
2. Every public function, class, and method has a docstring.
3. Every ``raise`` statement in a public function is documented in its docstring.

A passing test suite guarantees every public API surface is documented —
no need for code review to catch missing docstrings.

Cannot be automated (requires human judgment):
  - Docstring accuracy (does it describe the right behavior?)
  - Docstring completeness (are all edge cases mentioned?)
  - Natural-language quality (is it clear, concise, idiomatic?)
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "peerpedia_core"

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _all_modules() -> list[Path]:
    return sorted(ROOT.rglob("*.py"))


def _rel(f: Path) -> str:
    return str(f.relative_to(ROOT.parent))


def _is_public(name: str) -> bool:
    """Return True if *name* is a public (non-dunder, non-private) identifier."""
    if name.startswith("__") and name.endswith("__"):
        return False  # dunder method: __init__, __post_init__, __repr__, etc.
    if name.startswith("_"):
        return False  # private: _helper, _validate_id, etc.
    return True


def _public_defs(tree: ast.Module) -> list[tuple[ast.AST, str, int]]:
    """Yield (node, name, lineno) for public defs at module and class level only.

    Nested functions (closures inside other functions) are skipped — they are
    implementation details documented by their enclosing function's docstring.
    """
    results: list[tuple[ast.AST, str, int]] = []

    def _collect(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if _is_public(node.name):
                    results.append((node, node.name, node.lineno))
                # Recurse into class bodies (methods), but NOT into function bodies
                if isinstance(node, ast.ClassDef):
                    _collect(node.body)

    _collect(tree.body)
    return results


def _get_docstring(node: ast.AST) -> str | None:
    """Return the docstring of a function, class, or module node, or None."""
    return ast.get_docstring(node)


def _dir_contains_license_only(f: Path) -> bool:
    """Return True if *f* is an ``__init__.py`` that contains only a license header.

    These files are pure namespace markers — no code, no API surface to document.
    Requiring a module docstring for them is noise.
    """
    if f.name != "__init__.py":
        return False
    text = f.read_text().strip()
    # Remove the SPDX license comment block and whitespace
    lines = text.split("\n")
    code_lines = [l for l in lines
                  if l.strip()
                  and not l.strip().startswith("#")
                  and not l.strip().startswith('"""')
                  and not l.strip().startswith("'''")]
    return len(code_lines) == 0


def _raises_in_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Return exception class names that *node* directly raises.

    A "direct" raise is a ``raise`` statement at any depth inside *node*'s
    body — including inside try/except handlers — but EXCLUDING raise
    statements inside nested function/class definitions (those belong to
    the nested def, not to *node*).
    """
    exceptions: list[str] = []

    def _walk(stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue  # skip nested definitions — their raises are their own
            if isinstance(stmt, ast.Raise):
                exc = stmt.exc
                if exc is None:
                    # bare ``raise`` — re-raise, not a new exception
                    exceptions.append("(re-raise)")
                elif isinstance(exc, ast.Call):
                    if isinstance(exc.func, ast.Name):
                        exceptions.append(exc.func.id)
                    elif isinstance(exc.func, ast.Attribute):
                        exceptions.append(exc.func.attr)
            elif isinstance(stmt, ast.Try):
                # Walk the try body, each except handler body, orelse, finalbody
                _walk(stmt.body)
                for handler in stmt.handlers:
                    _walk(handler.body)
                _walk(stmt.orelse)
                _walk(stmt.finalbody)
                continue  # already recursed manually
            # Recurse into compound statements (if, for, while, with, match, etc.)
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, ast.stmt) and not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                ):
                    _walk([child])

    _walk(node.body)
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for e in exceptions:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# A. Module-level docstrings
# ═══════════════════════════════════════════════════════════════════════════════


def test_module_docstrings_present():
    """Every ``.py`` file must have a module-level docstring.

    Empty ``__init__.py`` files (license header only) are exempt — they are
    namespace markers with no API surface to document.
    """
    missing: list[str] = []
    for f in _all_modules():
        if _dir_contains_license_only(f):
            continue
        tree = ast.parse(f.read_text())
        if _get_docstring(tree) is None:
            missing.append(_rel(f))
    if missing:
        raise AssertionError(
            "Modules without module-level docstring:\n  "
            + "\n  ".join(missing)
            + "\n\nEvery .py file must have a module docstring explaining its purpose."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# B. Public function / class / method docstrings
# ═══════════════════════════════════════════════════════════════════════════════


def test_public_defs_have_docstrings():
    """Every public function, class, and method must have a docstring.

    "Public" means the name does not start with ``_`` (private) or ``__``
    (dunder methods).  A class having a docstring does not excuse its
    public methods from having one.
    """
    missing: list[str] = []

    for f in _all_modules():
        tree = ast.parse(f.read_text())
        for _node, name, lineno in _public_defs(tree):
            if _get_docstring(_node) is not None:
                continue
            missing.append(f"{_rel(f)}:{lineno}: {name}()")

    if missing:
        raise AssertionError(
            "Public functions/classes/methods without docstring:\n  "
            + "\n  ".join(missing)
            + "\n\nEvery public API surface must have a docstring."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# C. Raise statements documented
# ═══════════════════════════════════════════════════════════════════════════════


def test_raise_documented_in_docstring():
    """Public functions that ``raise`` must document it in their docstring.

    Checks the function's own docstring first.  If it does not mention
    "Raises", the *module* docstring is checked — if the module docstring
    names every exception class the function raises, the global convention
    covers the function.  This allows modules with consistent error patterns
    (e.g. all functions raise ``TransportError``) to document once rather
    than repeating the same ``Raises`` line 20 times.

    Bare ``raise`` (re-raise) is excluded — it continues an existing
    exception chain.

    Only checks functions that already have a docstring.  Functions without
    a docstring are caught by ``test_public_defs_have_docstrings``.
    """
    violations: list[str] = []

    for f in _all_modules():
        tree = ast.parse(f.read_text())
        module_doc = _get_docstring(tree) or ""

        for node, name, lineno in _public_defs(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # skip ClassDef nodes — raise check is for functions only

            doc = _get_docstring(node)
            if doc is None:
                continue  # caught by test_public_defs_have_docstrings

            raised = _raises_in_body(node)
            if not raised:
                continue

            # Bare re-raise only → skip (not a new exception surface)
            if raised == ["(re-raise)"]:
                continue

            # Check function docstring first
            if "raise" in doc.lower():
                continue

            # Check module docstring — does it name every exception?
            module_covers = all(exc in module_doc for exc in raised)
            if module_covers:
                continue

            violations.append(
                f"{_rel(f)}:{lineno}: {name}() raises {', '.join(raised)} "
                f"but neither function nor module docstring mentions it"
            )

    if violations:
        raise AssertionError(
            "Functions that raise but don't document it:\n  "
            + "\n  ".join(violations)
            + "\n\nEvery public function that raises must mention it in the docstring "
            '(e.g. "Raises ValueError if ..."), or the module docstring must name '
            "the exception class."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# D. Docstring path references — no stale file paths
# ═══════════════════════════════════════════════════════════════════════════════

import re

_DOCSTRING_PATH_RE = re.compile(r"``([^`]*/[^`]+\.py)``")


def _extract_path_refs(docstring: str, *, exclude_todo: bool = True) -> list[str]:
    """Extract file path references from a module docstring.

    Skips references inside ``.. todo::`` blocks — those are aspirational
    (files planned but not yet created), not stale.
    """
    text = docstring
    if exclude_todo:
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
        doc = _get_docstring(ast.parse(f.read_text()))
        if not doc:
            continue
        rel = _rel(f)
        for ref in _extract_path_refs(doc):
            if ref.startswith("peerpedia_core/"):
                target = ROOT.parent / ref
            else:
                target = ROOT / ref
            if not target.exists():
                raise AssertionError(
                    f"{rel}: docstring references ``{ref}`` — file not found"
                )
