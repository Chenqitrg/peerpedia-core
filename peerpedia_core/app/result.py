# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Structured result types returned by app commands.

``AppResult`` is the primary output — it carries a message code, structured
data, and optional format parameters.  ``AppNotice`` is a side notification
(e.g. "discovered 3 new articles during sync").

The CLI/REPL renderers map ``code`` to the message registry in ``messages.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AppNotice:
    """A side notification produced during command execution.

    Example: sync discovers new articles while publishing.
    """
    code: str
    params: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppResult:
    """The structured result of an app command.

    ``code`` matches a key in the message registry (``messages.py``).
    ``data`` is included in JSON output.
    ``params`` are format parameters for the message template.
    ``notices`` are side notifications (sync results, warnings, etc.).
    """
    code: str
    data: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    notices: list[AppNotice] = field(default_factory=list)
