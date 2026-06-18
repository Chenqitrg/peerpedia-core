# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared score types used across models."""

from dataclasses import dataclass


def _clamp(value: float, lo: float = 0.0, hi: float = 5.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class FiveDimScores:
    """Five-dimensional article scores (1.0-5.0 each)."""

    originality: float = 0.0
    rigor: float = 0.0
    completeness: float = 0.0
    pedagogy: float = 0.0
    impact: float = 0.0

    def __post_init__(self):
        self.originality = _clamp(self.originality)
        self.rigor = _clamp(self.rigor)
        self.completeness = _clamp(self.completeness)
        self.pedagogy = _clamp(self.pedagogy)
        self.impact = _clamp(self.impact)

    def average(self) -> float:
        return (self.originality + self.rigor + self.completeness + self.pedagogy + self.impact) / 5.0

    def weighted_average(self, weights: list[float]) -> float:
        """Weighted average with given dimension weights (5 floats)."""
        values = [self.originality, self.rigor, self.completeness, self.pedagogy, self.impact]
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        return sum(v * w for v, w in zip(values, weights)) / total_weight

    def to_dict(self) -> dict:
        return {
            "originality": self.originality,
            "rigor": self.rigor,
            "completeness": self.completeness,
            "pedagogy": self.pedagogy,
            "impact": self.impact,
        }


@dataclass
class ReputationScores:
    """Four-dimensional user reputation scores."""

    professionalism: float = 0.0
    objectivity: float = 0.0
    collaboration: float = 0.0
    pedagogy: float = 0.0

    def average(self) -> float:
        return (self.professionalism + self.objectivity + self.collaboration + self.pedagogy) / 4.0

    def to_dict(self) -> dict:
        return {
            "professionalism": self.professionalism,
            "objectivity": self.objectivity,
            "collaboration": self.collaboration,
            "pedagogy": self.pedagogy,
        }
