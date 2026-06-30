# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Structured output formatting — the single exit point for all CLI output.

Every user-facing message goes through ``_out()``, which dispatches on
message kind (SUCCESS / ERROR / NOTIFY) and output mode (--json / --rich).
There are exactly two other public functions:

* ``_render_result(args, result)`` — render an ``AppResult``
* ``_render_error(args, error)``   — render a ``PeerpediaError``

Both delegate to ``_out()`` as the single terminal.
"""

from __future__ import annotations

import json
import logging as _logging
import os
import subprocess
import sys
from rich.console import Console
from rich.theme import Theme

from peerpedia_core.messages import Kind, log_text as _log_text, lookup as _lookup
from peerpedia_core.presentation.rich.components import error_lines

# ── Rich console (singleton) ──────────────────────────────────────────────
# Only output.py owns the Console instance — all other CLI modules go through
# the wrapper functions below.

theme = Theme({
    "success": "#777C5C bold",    # olive
    "error": "#B84040 bold",      # brick red
    "warning": "#D4893C bold",    # amber
    "info": "#A85F3B bold",       # primary terracotta
    "accent": "#B08A57 bold",     # gold-brown
    "muted": "#6F665E dim",       # warm gray
})

console = Console(theme=theme)


# ── Terminal / OS helpers ─────────────────────────────────────────────────


def _open_file(path: str) -> None:
    """Open a file with the system default application."""
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — intentional user-facing file open
    else:
        subprocess.run(["xdg-open", path])


def _page(text: str) -> None:
    """Display text through a pager (``$PAGER`` or ``less -R``)."""
    pager = os.environ.get("PAGER", "less -R")
    try:
        subprocess.run(pager.split(), input=text, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print(text)


# ── Low-level output primitives ──────────────────────────────────────────


def _ok(what: str) -> None:
    """Success message with green checkmark (raw — prefer ``_out()``)."""
    console.print(f"✓ [{theme.styles['success']}]{what}[/]")


def _json_out(data: dict | list) -> None:
    """Machine-readable output, used when --json is passed."""
    print(json.dumps(data, indent=2, default=str))


def _render_data(data) -> None:
    """Render a data-only (empty-code) result in Rich mode.

    Emitted when an ``AppResult("", data=...)`` reaches the CLI.
    Dicts → key-value Panel, lists of dicts → Table, scalars → inline.
    """
    if isinstance(data, list) and data and isinstance(data[0], dict):
        _render_table(data)
    elif isinstance(data, dict):
        _render_key_value_pairs(data)
    elif isinstance(data, list):
        for item in data:
            console.print(f"  — {item}")
    else:
        console.print(data)


def _render_table(rows: list[dict]) -> None:
    """Render a list of dicts as a Rich Table."""
    from rich.table import Table

    # ── Infer columns from first row keys ──
    keys = list(rows[0].keys())
    table = Table(border_style="muted")
    for k in keys:
        table.add_column(k, style="bold" if k == keys[0] else "")
    for row in rows:
        table.add_row(*[str(row.get(k, "")) for k in keys])
    console.print(table)


def _render_key_value_pairs(data: dict) -> None:
    """Render a dict as key-value pairs in a panel."""
    from rich.panel import Panel
    lines = []
    for k, v in data.items():
        if v is not None and v != "":
            lines.append(f"[bold]{k}[/]: {v}")
    if lines:
        console.print(Panel("\n".join(lines), border_style="muted"))


# ── Core dispatch ────────────────────────────────────────────────────────


def _out(args, code: str, data=None, /, **fmt):
    """Single output entry point.  Dispatches on message kind.

    ``_out(args, "REGISTERED", {"id": uid}, name="Alice")``  → success
    ``_out(args, "AUTH_FAILED")``                              → error (die)
    ``_out(None, "W_NO_KNOWN_PEERS")``                         → notify (display only)
    ``_out(args, "UNKNOWN_CODE")``                             → error (unregistered → ERROR fallback)
    """
    code, m = _lookup(code)
    use_json = args is not None and getattr(args, "json", False)

    # ── Error ──
    if m.kind == Kind.ERROR:
        _render_error_out(code, m, use_json, fmt)
        sys.exit(1)

    # ── Notify ──
    if m.kind == Kind.NOTIFY:
        if not use_json and m.text:
            console.print(_format(m.text, fmt))
        return

    # ── Success ──
    if use_json:
        payload: dict = {"code": code}
        if isinstance(data, dict):
            payload.update(data)
        elif isinstance(data, list):
            payload["items"] = data
        elif data is not None:
            payload["value"] = data
        _json_out(payload)
        sys.exit(0)
    if m.text:
        _ok(_format(m.text, fmt))
    elif data is not None:
        _render_data(data)


def _render_error_out(code: str, m, use_json: bool, fmt: dict) -> None:
    """Render an ERROR message — shared by ``_out()`` and ``_render_error()``."""
    msg = _format(m.text, fmt)
    suggestion = _format(m.suggestion, fmt) if m.suggestion else ""
    see_also = m.see_also

    if use_json:
        payload: dict = {"error": code, "message": msg}
        if suggestion:
            payload["suggestion"] = suggestion
        if see_also:
            payload["see_also"] = list(see_also)
        print(json.dumps(payload, indent=2, default=str))
        return

    for line in error_lines(msg, suggestion=suggestion, see_also=see_also or ()):
        console.print(line)


# ── AppResult / AppError renderers ───────────────────────────────────────


def _render_result(args, result) -> None:
    """Render an ``AppResult`` to stdout via ``_out()``.

    Notices are rendered first (Rich only), then the main result.
    """
    use_json = args is not None and getattr(args, "json", False)
    if not use_json:
        for notice in getattr(result, "notices", []):
            _out(None, notice.code, notice.data, **notice.params)
    _out(args, result.code, result.data, **result.params)


def _render_error(args, error) -> None:
    """Render a ``PeerpediaError`` to stdout.

    Delegates to ``_render_error_out`` — the single error renderer.
    ``error.context`` becomes format parameters for the message template.
    """
    code, m = _lookup(error.code)
    use_json = args is not None and getattr(args, "json", False)
    ctx = dict(getattr(error, "context", {}))
    if hasattr(error, "detail") and error.detail:
        ctx.setdefault("detail", str(error.detail))
    _render_error_out(code, m, use_json, ctx)


# ── Logging (no args, no exit) ───────────────────────────────────────────


def _log(code: str, *, level: str = "info", **fmt):
    """Log a structured message by code.  For background/daemon code.

    ``_log("L_SYNC_FAILED", server=srv, error=e)``
    """
    text = _log_text(code, **fmt)
    getattr(_logging.getLogger("peerpedia_core.cli"), level)(text)


# ── Internal ─────────────────────────────────────────────────────────────


def _format(template: str, fmt: dict) -> str:
    """Format a template string with *fmt* parameters.

    Missing keys are left as-is (e.g. ``{name}`` stays ``{name}``)
    instead of raising KeyError — the message template and the
    exception context may not always agree on key names.
    """
    if not fmt:
        return template
    import string
    return string.Formatter().vformat(template, (), _SafeDict(fmt))


class _SafeDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"
