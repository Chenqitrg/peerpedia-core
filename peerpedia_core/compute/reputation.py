# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Reputation mechanism — pure computation, zero storage dependencies.

.. warning::

    **This entire module is a placeholder.**  Both the algorithm and the
    dimension set are provisional.  There is no ground truth for "academic
    quality" — it is an institutional fact (a social convention, not a
    physical measurement).  Every scoring system, from peer review to
    h-index, is a consensus, not a sensor reading.

    Target dimensions (after bootstrapping):
        professionalism, pedagogy, collaboration, credibility, taste

    The current 5→4 mapping and the EMA blend are stubs.  Replace wholesale
    when real data flows in, or fork the module to run competing definitions
    side by side.

Full design: docs/reputation-v2-plan.md
Architecture rationale: workflow/state.py

Isolation boundary
------------------
Input: ``ReputationState`` (immutable snapshot, no DB handles).
Output: ``ReputationScores`` (dataclass).

The orchestrator in ``commands/workflow.py`` calls ``extract_state`` to
build a State from the DB, then passes it here.  Tests construct State
directly.  To swap the algorithm: replace the function bodies, keep the
signatures.  To run MULTIPLE algorithms simultaneously: instantiate a
second module with the same interface — the rest of the system is
algorithm-agnostic.

Public interface (3 functions):
    compute_reputation(state, user_id) → ReputationScores
    blend_reputation(existing, new, weight?) → ReputationScores
    get_reviewer_weight(reputation) → float

Dimension mapping (5 article dims → 4 reputation dims, PLACEHOLDER)
--------------------------------------------------------------------
    professionalism ← avg(originality, rigor)
    objectivity    ← completeness
    collaboration  ← avg(originality, impact)
    pedagogy       ← pedagogy (1:1)
"""

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TODO(MVP-post): Review-pedagogy via git-commit attribution                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# Core insight: the only unforgeable signal that a review was substantive is
# whether the AUTHOR acted on it.  Scores, word counts, and AI-generated text
# are all gameable.  A git diff is not — the author must write real changes.
#
# ── Mechanism ─────────────────────────────────────────────────────────────────
#
# 1. TRAILER CONVENTION
#    After receiving a review, the author commits changes and includes:
#
#        Acked-by: alice <alice-uuid@peerpedia>
#        Closes: review/alice/thread-3
#
#    ``Acked-by:`` acknowledges the reviewer.  ``Closes:`` links to the
#    specific review thread (already stored in git as
#    ``reviews/{reviewer_id}/threads/*.md``).
#
# 2. SYSTEM SCANS COMMIT MESSAGES (no NLP, no AI)
#    For each commit in the article repo that falls within the sedimentation
#    window and contains ``Closes:``:
#
#        reviewer_id = parse(commit.message, "Closes:")
#        diff_size    = commit.stats.total["lines"]
#        hunks        = len(commit.stats.files)
#
#    Threshold: diff_size ≥ 20 lines OR hunks ≥ 3.  Below this, the commit
#    is treated as a cosmetic change and does NOT trigger a pedagogy event.
#
# 3. REVIEWER PEDAGOGY INCREASES
#    Each qualifying commit → reviewer.pedagogy += δ (small, capped per review).
#    A reviewer whose feedback causes substantial revision accumulates
#    pedagogy over time.  pedagogy is now observable (commit count, diff
#    volume) rather than self-reported.
#
# 4. AUTHOR PROFESSIONALISM MICRO-DECREASE
#    Each qualifying commit → author.professionalism -= ε (very small).
#    Rationale: submitting a draft that requires major revision is a
#    professionalism signal — but the penalty is TINY compared to what
#    happens if the article is published with undetected problems.
#
#    | Scenario                              | Penalty                    |
#    |---------------------------------------|----------------------------|
#    | Reviewer catches issue → author fixes | professionalism: -0.01     |
#    | Article published with major error    | professionalism: -0.5      |
#    |                                       | credibility:   -0.3       |
#    |                                       | article:       fold       |
#
#    The author's rational choice: fix it now.  The reviewer is not doing
#    charity — they are providing an escape hatch from much worse outcomes.
#
# ── Why this resists gaming ──────────────────────────────────────────────────
#
# | Attack                                    | Defense                           |
# |-------------------------------------------|-----------------------------------|
# | Author adds Closes: without changing code | diff is empty → rejected          |
# | Author + reviewer collude, change 1 char  | diff below threshold → rejected   |
# | Author cites an old review               | review timestamp > commit ts → rej |
# | AI generates review text                 | doesn't matter — only diff counts |
# | Author self-reviews and self-Closes:     | is_self check → rejected          |
# | Author rewrites entire article           | professionalism: -0.01 per commit |
# |                                           | — cumulative signal, not punitive |
#
# ── Game-theoretic closure ───────────────────────────────────────────────────
#
# Nobody needs altruism:
#
#   • Author submits draft.  If sloppy → reviewer finds issues → author fixes.
#     Cost: tiny professionalism dip.  Benefit: avoids post-publish disaster.
#
#   • Reviewer gives specific feedback.  Author acts on it → reviewer gains
#     pedagogy.  Benefit: pedagogy → higher nomination weight → more review
#     requests → more pedagogy.  Self-reinforcing loop.
#
#   • Author resists fixing.  Reviewer's feedback is public (in thread).  If
#     article later folds due to an issue the reviewer flagged and the author
#     ignored → author's credibility tanks.  Community can see the trail.
#
# ── Implementation notes ─────────────────────────────────────────────────────
#
# • No new database tables needed.  Review threads already live in git
#   (reviews/{reviewer_id}/threads/).  Commit trailers are parsed from
#   existing git history via ``iter_commits()``.
#
# • The scan function belongs in ``commands/`` (orchestrator).  It calls
#   a pure function in ``workflow/`` that takes (reviewer_id, commits, diff_stats)
#   and returns pedagogy deltas.  State stays clean.
#
# • Trigger: ``accept_merge``, ``publish_article``, and periodic integrity
#   repair should all scan for unprocessed Closes: trailers.
#
# • Configurable knobs (add to params.py):
#     - pedagogy.delta_per_commit: float = 0.05
#     - professionalism.delta_per_revision: float = -0.01
#     - diff.min_lines: int = 20
#     - diff.min_hunks: int = 3

from peerpedia_core.config.params import params
from peerpedia_core.types.scores import FiveDimScores, ReputationScores
from peerpedia_core.compute.state import ReputationState

# Field names derived from dataclasses — single source of truth, never hardcoded.
_REP_FIELDS = tuple(ReputationScores.__dataclass_fields__.keys())
_ARTICLE_DIMS = set(FiveDimScores.__dataclass_fields__.keys())

# Status-based weights for article scoring in reputation.
# Published articles carry the most weight.
_STATUS_WEIGHTS = {
    "published": 1.0,
    "sedimentation": 0.7,
    "draft": 0.3,
}

# Mapping from the 5 article-score dimensions to the 4 reputation dimensions.
_REP_DIMS: dict[str, list[str]] = {
    "professionalism": ["originality", "rigor"],
    "objectivity": ["completeness"],
    "collaboration": ["originality", "impact"],
    "pedagogy": ["pedagogy"],
}

# Fail fast if _REP_DIMS drifts from dataclass fields.
assert set(_REP_DIMS) == set(_REP_FIELDS), \
    f"_REP_DIMS keys {set(_REP_DIMS)} != ReputationScores fields {set(_REP_FIELDS)}"
for rep_dim, article_dims in _REP_DIMS.items():
    unknown = set(article_dims) - _ARTICLE_DIMS
    assert not unknown, \
        f"_REP_DIMS['{rep_dim}'] references unknown article dims: {unknown}"


def compute_reputation(state: ReputationState, user_id: str) -> ReputationScores:
    """Compute raw reputation for *user_id* from an immutable State snapshot.

    Gathers all articles authored by *user_id* from *state* and aggregates
    their scores into reputation dimensions.  Returns all zeros if the user
    has no articles with scores.
    """
    dim_totals = {f: 0.0 for f in _REP_FIELDS}
    total_weight = 0.0

    for article in state.articles.values():
        if user_id not in article.author_ids:
            continue
        score = article.score
        if not score:
            continue
        status_w = _STATUS_WEIGHTS.get(article.status, 0.3)

        for rep_dim, article_dims in _REP_DIMS.items():
            values = [score.get(d, 0.0) for d in article_dims]
            dim_totals[rep_dim] += (sum(values) / len(values)) * status_w

        total_weight += status_w

    if total_weight == 0:
        return ReputationScores()

    return ReputationScores(**{
        f: round(dim_totals[f] / total_weight, 2) for f in _REP_FIELDS
    })


def blend_reputation(
    existing: dict,
    new: ReputationScores,
    weight: float | None = None,
) -> ReputationScores:
    """Blend new reputation scores with existing ones using EMA smoothing.

    *existing* is the current reputation dict (may be empty).
    *weight* defaults to params.reputation.article_to_author_weight.
    """
    if weight is None:
        weight = params.reputation.article_to_author_weight

    kwargs = {}
    for f in _REP_FIELDS:
        old_val = existing.get(f, 0.0)
        new_val = getattr(new, f)
        kwargs[f] = round((1 - weight) * old_val + weight * new_val, 2)
    return ReputationScores(**kwargs)


def get_reviewer_weight(reputation: dict | None) -> float:
    """Return a weight factor for a reviewer based on their reputation.

    Defaults to 1.0 when reputation is None or empty.
    """
    if not reputation:
        return 1.0

    rep = ReputationScores(**{f: reputation.get(f, 0.0) for f in _REP_FIELDS})

    avg_rep = rep.average()
    weight = 1.0 + params.reputation.author_weight_in_review * (avg_rep - 3.0) / 2.0
    return max(0.0, weight)
