# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Structured output formatting — the single exit point for all CLI output.

Layer 1 of the CLI package.  Imports from ``display`` (Layer 0) and
``msgs`` (Layer 1).  Does NOT import from ``helpers``, ``bundle_utils``,
``handlers``, or ``parser`` — zero risk of circular dependency.

Every message goes through ``_out()``, which dispatches on message kind
(SUCCESS / ERROR / NOTIFY) and output mode (--json / --rich).
"""

from __future__ import annotations

import contextvars
import json
import logging as _logging
import sys

from rich.text import Text

from peerpedia_core.cli.display import console, theme
from peerpedia_core.messages import Kind, log_text as _log_text, lookup as _lookup

# ── JSON mode context ─────────────────────────────────────────────────────

# Whether the current handler was invoked with --json.  Set by _with_db
# before the handler runs; read by _die to decide output format.
_die_json_mode: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_die_json_mode", default=False,
)


def _set_die_json_mode(enabled: bool) -> None:
    """Set JSON mode for the current handler context (used by _with_db)."""
    _die_json_mode.set(enabled)


# ── Terminal / OS helpers ─────────────────────────────────────────────────


from peerpedia_core.cli.display import _page  # re-export for backward compat


def _open_file(path: str) -> None:
    """Open a file with the system default application."""
    import os
    import subprocess
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — intentional user-facing file open
    else:
        subprocess.run(["xdg-open", path])


# ── Core output functions ─────────────────────────────────────────────────


def _ok(what: str) -> None:
    """Success message with green checkmark."""
    console.print(f"✓ [{theme.styles['success']}]{what}[/]")


def _json_out(data: dict | list) -> None:
    """Machine-readable output, used when --json is passed."""
    print(json.dumps(data, indent=2, default=str))


def _out_error_raw(msg: str, **kwargs):
    """Fallback for old-style _die calls with literal messages.  No registry lookup."""
    code = kwargs.pop("code", "ERROR")
    if _die_json_mode.get():
        payload: dict = {"error": code, "message": msg}
        if kwargs:
            payload.update(kwargs)
        print(json.dumps(payload, indent=2, default=str))
        sys.exit(1)
    console.print(Text(f"✗ {msg}", style=theme.styles["error"]))
    suggestion = kwargs.get("suggestion", "")
    if suggestion:
        console.print()
        console.print(f"  [dim]→ {suggestion}[/]")
    sys.exit(1)


def _die(code_or_msg: str = "INTERNAL_ERROR", /, **fmt):
    """Backward-compat wrapper — delegates to ``_out(None, code, **fmt)``.

    Prefer ``_out(args, code, data, **fmt)`` in new code.
    """
    code, m = _lookup(code_or_msg)
    if m.text != code_or_msg:
        _out(None, code, **fmt)
    else:
        _out_error_raw(code_or_msg, **fmt)


def _out(args, code: str, data=None, /, **fmt):
    """Single output entry point.  Dispatches on message kind.

    ``_out(args, "REGISTERED", {"id": uid}, name="Alice")``  → success
    ``_out(args, "AUTH_FAILED")``                              → error (die)
    ``_out(None, "AUTH_FAILED")``                              → error, no JSON
    ``_out(args, "", data)``                                   → JSON-only (no message)
    """
    if not code:
        if args is not None and getattr(args, "json", False):
            _json_out(data)
            sys.exit(0)
        return
    code, m = _lookup(code)
    use_json = args is not None and getattr(args, "json", False)

    if m.kind == Kind.ERROR:
        msg = m.text.format(**fmt) if fmt else m.text
        if _die_json_mode.get() and use_json:
            payload: dict = {"error": m.code, "message": msg}
            if m.suggestion:
                payload["suggestion"] = m.suggestion.format(**fmt) if fmt else m.suggestion
            if m.see_also:
                payload["see_also"] = list(m.see_also)
            print(json.dumps(payload, indent=2, default=str))
            sys.exit(1)
        console.print(Text(f"✗ {msg}", style=theme.styles['error']))
        if m.suggestion:
            console.print()
            console.print(f"  [dim]→ {m.suggestion.format(**fmt) if fmt else m.suggestion}[/]")
        if m.see_also:
            console.print(f"  [muted]See also: {' · '.join(m.see_also)}[/]")
        sys.exit(1)

    if m.kind == Kind.NOTIFY:
        # Display-only — JSON mode skips, pretty prints and continues.
        if not use_json and m.text:
            console.print(m.text.format(**fmt) if fmt else m.text)
        return

    # ── Success path ────────────────────────────────────────────────────
    if use_json:
        payload: dict = {"code": m.code}
        if isinstance(data, dict):
            payload.update(data)
        elif isinstance(data, list):
            payload["items"] = data
        elif data is not None:
            payload["value"] = data
        _json_out(payload)
        sys.exit(0)
    if m.text:
        _ok(m.text.format(**fmt) if fmt else m.text)


def _log(code: str, *, level: str = "info", **fmt):
    """Log a structured message by code.  For background/daemon code.

    ``_log("L_SYNC_FAILED", server=srv, error=e)``
    """
    text = _log_text(code, **fmt)
    getattr(_logging.getLogger("peerpedia_core.cli"), level)(text)


# ── Shared CLI display patterns ───────────────────────────────────────────


def _empty_state(message: str) -> None:
    """Print a muted empty-state message."""
    console.print(f"[muted]{message}[/]")


def _show(args, code: str = "", data=None, /, **fmt):
    """Backward-compat wrapper — delegates to ``_out(args, code, data, **fmt)``."""
    _out(args, code, data, **fmt)


def _output_result(args, result: dict, success_msg: str) -> None:
    """Output a command result as JSON or a styled success message.

    Replaces the repeated ``if args.json: _json_out(result); else: _ok(...)``
    pattern that appears in 8+ handlers.
    """
    if getattr(args, "json", False):
        _json_out(result)
    else:
        _ok(success_msg)


# ── AppResult / AppError renderers ────────────────────────────────────────


def _render_result(args, result) -> None:
    """Render an ``AppResult`` to stdout via ``_out()``.

    Notices are rendered first (Rich only), then the main result.
    JSON mode: only the main result code + data, exit 0.
    """
    use_json = args is not None and getattr(args, "json", False)
    # ── Notices (Rich only) ──
    if not use_json:
        for notice in getattr(result, "notices", []):
            _out(None, notice.code, notice.data, **notice.params)
    # ── Main result ──
    _out(args, result.code, result.data, **result.params)


def _render_error(args, error) -> None:
    """Render a ``PeerpediaError`` to stdout via ``_out()``.

    Uses ``error.code`` to look up the message registry.  Context dict
    becomes format parameters.  JSON mode includes the full payload.
    """
    use_json = args is not None and getattr(args, "json", False)
    ctx = getattr(error, "context", {})
    if use_json:
        payload: dict = {"error": error.code, "message": str(error)}
        if ctx:
            payload.update(ctx)
        print(json.dumps(payload, indent=2, default=str))
        sys.exit(1)
    _out(None, error.code, **ctx)
