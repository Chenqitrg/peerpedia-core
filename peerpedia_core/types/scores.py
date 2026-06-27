# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared score types used across models.

.. warning::

    FiveDimScores and ReputationScores are bootstrapping artifacts.

    "Academic quality" is an institutional fact (Searle): it exists because
    a community collectively treats it as real — like money, not like mass.
    No scoring system measures it; every system defines what it means to
    measure it.  Peer review, h-index, journal impact factor — all are
    social conventions, not sensors.

    These human-readable dimensions (originality, professionalism, ...)
    exist so the system can cold-start before ML training data exists.
    Long-term, an LLM learns its own latent embeddings from raw events
    (review text, edit diffs, share chains, citation graphs).  The named
    dimensions become one possible projection layer — useful for debugging,
    not the final representation.

    The architecture supports competing definitions: fork the scoring
    module, change the dimensions, run both side by side.  The rest of
    the system does not depend on which definition wins.

    See workflow/state.py for the ML interface and the performative
    prediction problem.
"""

from dataclasses import dataclass

# Five review dimensions — change here, everything updates.
# Keys = CLI abbreviation, values = display name.
# TODO(MVP-post): replace "impact" with "insight" (启发性) in reviewer scores.
# Impact should be a derived metric (citations, forks, shares), not something
# reviewers guess at review time.  Also add ImpactScores dataclass for the
# derived metric.  Full plan: docs/reputation-v2-plan.md
SCORE_DIMENSIONS: dict[str, str] = {
    "orig":  "originality",
    "rigor":  "rigor",
    "comp":   "completeness",
    "ped":   "pedagogy",
    "imp":   "impact",
}

# Example for CLI help text: "orig=4,rigor=3,comp=4,ped=3,imp=3"
SCORE_FORMAT_EXAMPLE = ",".join(f"{abbr}=N" for abbr in SCORE_DIMENSIONS)
# Human-readable dimension guide for --help output.
# e.g. "orig (originality), rigor (rigor), comp (completeness), ped (pedagogy), imp (impact)"
_SCORE_DIMS_LIST = ", ".join(
    f"{abbr}={full}" for abbr, full in SCORE_DIMENSIONS.items()
)


def normalize_score_keys(scores: dict) -> None:
    """Mutate *scores* in place: replace abbreviation keys with full dimension names.

    >>> s = {"orig": 4, "rigor": 3}
    >>> normalize_score_keys(s)
    >>> s
    {'originality': 4, 'rigor': 3}
    """
    for abbr, full in SCORE_DIMENSIONS.items():
        if abbr in scores and full not in scores:
            scores[full] = scores.pop(abbr)


def _clamp(value: float, lo: float = 0.0, hi: float = 5.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class FiveDimScores:
    """Article review scores (1.0-5.0 each).

    .. todo:: MVP-post

        Replace ``impact`` with ``insight``.  Impact will be a separately
        computed derived metric (citations, forks, shares), not part of
        reviewer scores.  See docs/reputation-v2-plan.md.
    """

    originality: float = 0.0
    rigor: float = 0.0
    completeness: float = 0.0
    pedagogy: float = 0.0
    impact: float = 0.0

    @property
    def _fields(self):
        return tuple(self.__dataclass_fields__.keys())

    def __post_init__(self):
        for f in self._fields:
            setattr(self, f, _clamp(getattr(self, f)))

    def average(self) -> float:
        """Return the arithmetic mean of all dimension scores."""
        values = [getattr(self, f) for f in self._fields]
        return sum(values) / len(values) if values else 0.0

    def weighted_average(self, weights: list[float]) -> float:
        """Weighted average with given dimension weights (must match field count)."""
        values = [getattr(self, f) for f in self._fields]
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        return sum(v * w for v, w in zip(values, weights)) / total_weight

    def to_result(self) -> dict:
        """Return scores as a plain dict keyed by dimension abbreviation."""
        return {f: getattr(self, f) for f in self._fields}


@dataclass
class ReputationScores:
    """User reputation scores.

    .. todo:: MVP-post

        Target dimensions: professionalism, pedagogy, collaboration,
        credibility, taste.  Current set is a placeholder — change the
        dataclass fields, NOT the consumers.  All consumers derive field
        names from ``__dataclass_fields__`` (no hardcoding).
    """

    professionalism: float = 0.0
    objectivity: float = 0.0      # TODO: replace with credibility
    collaboration: float = 0.0
    pedagogy: float = 0.0         # TODO: add taste

    @property
    def _fields(self):
        return tuple(self.__dataclass_fields__.keys())

    def average(self) -> float:
        """Return the arithmetic mean of all reputation dimensions."""
        values = [getattr(self, f) for f in self._fields]
        return sum(values) / len(values) if values else 0.0

    def to_result(self) -> dict:
        """Return reputation scores as a plain dict keyed by dimension name."""
        return {f: getattr(self, f) for f in self._fields}
