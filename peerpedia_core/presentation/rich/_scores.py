# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Score rendering — stars and plain-text lines."""

from __future__ import annotations

from peerpedia_core.types.scores import SCORE_DIMENSIONS

SCORE_DIM_NAMES: list[str] = list(SCORE_DIMENSIONS.values())

_DIM_LABEL_WIDTH = 14
_MAX_SCORE = 5


def score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
    """Return one plain-text line per dimension, e.g. ``'originality    ★★★☆☆  3/5'``."""
    if not score:
        return ["—"]
    if dims is None:
        dims = SCORE_DIM_NAMES
    return [
        f"  {d:<{_DIM_LABEL_WIDTH}} {'★'*v}{'☆'*(_MAX_SCORE-v)}  {v}/{_MAX_SCORE}"
        for d in dims
        for v in [int(score.get(d, 0))]
    ]


def score_stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores with Rich markup, e.g. ``[accent]★★★★☆[/][muted]☆[/]  4/5``."""
    if not score:
        return "[muted]no score[/]"
    if dims is None:
        dims = SCORE_DIM_NAMES
    return "\n".join(
        f"  {d:<{_DIM_LABEL_WIDTH}} [accent]{'★'*v}[/][muted]{'☆'*(_MAX_SCORE-v)}[/]  {v}/{_MAX_SCORE}"
        for d in dims
        for v in [int(score.get(d, 0))]
    )
