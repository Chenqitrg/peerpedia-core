# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Terminal input utilities — editor prompts, password input.

Pure infrastructure — no ``_out()``, no ``sys.exit()``.  Raises exceptions
for the caller to handle.  CLI handlers import and wrap these for
``_out()`` calls.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from peerpedia_core.exceptions import BadRequestError

_EDITOR_ENV = "EDITOR"
_EDITOR_DEFAULT = "vim"
_DIFF_SUFFIX = ".diff"

_COMMIT_MSG_HEADER = (
    "\n# Please enter a commit message for your changes.\n"
    "# Lines starting with '#' will be ignored.\n"
    "# An empty message aborts the commit.\n"
    "#\n"
)
_COMMIT_MSG_DIFF_PREFIX = "# Changes:\n#\n"


def _format_diff_header(diff: str) -> str:
    """Build the ``# Changes:`` section of the commit message template."""
    return _COMMIT_MSG_DIFF_PREFIX + "# " + "\n# ".join(diff.splitlines()) + "\n"


def get_password(args, confirm: bool = False) -> str:
    """Read password from --password, env, or TTY prompt.

    Raises BadRequestError on empty/mismatched password or missing TTY.
    """
    pw = getattr(args, "password", None) or os.environ.get("PEERPEDIA_PASSWORD")
    if pw:
        return pw
    if not sys.stdin.isatty():
        raise BadRequestError(code="NO_TTY")
    password = getpass.getpass("Password: ")
    if not password:
        raise BadRequestError(code="EMPTY_PASSWORD")
    if confirm:
        again = getpass.getpass("Confirm password: ")
        if password != again:
            raise BadRequestError(code="PASSWORD_MISMATCH")
    return password


def open_editor(initial: str, *, suffix: str = ".md") -> str:
    """Open $EDITOR (defaults to vim) and return the edited text.

    *suffix* controls temp file extension for syntax highlighting.
    Raises BadRequestError if there is no TTY.
    """
    if not sys.stdin.isatty():
        raise BadRequestError(code="NO_TTY_EDITOR")
    editor = os.environ.get(_EDITOR_ENV, _EDITOR_DEFAULT)
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(initial)
        f.flush()
        subprocess.call([editor, f.name])
        return Path(f.name).read_text()


def _strip_comments(text: str) -> str:
    """Remove ``#`` comment lines and surrounding whitespace."""
    lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    return "\n".join(lines).strip()


def prompt_commit_message(diff: str = "") -> str:
    """Open ``$EDITOR`` to get a commit message, like ``git commit``.

    Builds a header template with optional diff, delegates to
    ``open_editor()``, then strips ``#`` comment lines.  Raises
    BadRequestError on empty message.
    """
    header = _COMMIT_MSG_HEADER
    if diff:
        header += _format_diff_header(diff)
    msg = _strip_comments(open_editor(header, suffix=_DIFF_SUFFIX))
    if not msg:
        raise BadRequestError(code="EMPTY_COMMIT_MSG")
    return msg
