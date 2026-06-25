# Reputation Model v2 — Full Signal Map & Implementation Plan

## Context

Current reputation is a one-way pipeline: `review scores → article score → author reputation`. It ignores review count, review accuracy, self-review honesty, social graph signals, share propagation, and collaborative behaviors. The goal is to design a multi-signal reputation model where every user action feeds back into the four dimensions (professionalism, objectivity, collaboration, pedagogy) through bidirectional feedback loops.

## The Full Signal Map

### Four Reputation Dimensions

| Dimension | Meaning | Positive Signal | Negative Signal |
|-----------|---------|----------------|-----------------|
| **professionalism** | Quality of work + accuracy of judgment | High article scores, accurate reviews, honest self-reviews | Low article scores, inaccurate reviews, inflated self-reviews |
| **objectivity** | Fairness, resistance to bias | Many reviews received, review scores match consensus, diverse reviewing targets | Always extreme scores (1 or 5), only reviewing friends, biased self-reviews |
| **collaboration** | Working well with others | Forks merged, reviews not overly harsh, co-authorship, articles forked by others | Harsh review scores, forks rejected, toxic interaction patterns |
| **pedagogy** | Ability to teach, guide, and discover | Reviews lead to author edits, shares get reshared, followers gained after reviews, good citation curation | Shares ignored, reviews that never cause improvement, poor citations |

### All Signal Sources (existing + proposed)

```
                         ┌───────────────────────┐
                         │    ReputationScores    │
                         │  (4 dims, per user)    │
                         └───────┬───────┬───────┘
                                 │       │
          ┌──────────────────────┼───────┼──────────────────────┐
          │                      │       │                      │
          ▼                      ▼       ▼                      ▼
   professionalism        objectivity  collaboration        pedagogy
          │                      │       │                      │
          │  article scores ─────┤       │                      │
          │  review accuracy ────┤       │                      │
          │  self-review gap ────┼───────┤                      │
          │  citation prestige ──┤       │                      │
          │                      │       │                      │
          │           review count ──────┤                      │
          │           review variance ───┤                      │
          │           review diversity ──┤                      │
          │           follower prestige ─┤                      │
          │                             │                       │
          │                    forks merged ────────────────────┤
          │                    co-authorship ───────────────────┤
          │                    review harshness ────────────────┤
          │                    articles forked by others ───────┤
          │                                                     │
          │                    review → author edits ───────────┤
          │                    share reshare depth ─────────────┤
          │                    followers gained ────────────────┤
          │                    citation curation ───────────────┤
          └─────────────────────────────────────────────────────┘
```

### Feedback Loops

**Loop 1 (exists):** reputation → `get_reviewer_weight(rep)` → review weight in `aggregate_review_scores` → article score → `compute_reputation` → reputation. This is a **convergent** loop (EMA dampens oscillation) but can create rich-get-richer effects.

**Loop 2 (proposed):** reputation → follower decisions → follower prestige → reputation. Being followed by high-rep users boosts your rep. This is **PageRank-like** — prestige flows through the social graph.

**Loop 3 (proposed):** review accuracy → professionalism/objectivity → review weight → article score → review accuracy (next cycle). Reviewers who are accurate get more weight, amplifying their future impact.

**Loop 4 (proposed):** share → reshare → pedagogy → review weight → more visibility → more shares. High-pedagogy users' shares get more attention.

### Anti-Gaming Mechanisms

| Attack | Defense |
|--------|---------|
| Sybil review rings | `review_diversity` penalty: if you only review articles by people you follow (or who follow you), objectivity drops. Social graph distance can detect collusion rings. |
| Review bombing | `review_accuracy` back-check: if your scores deviate far from the final community consensus, your professionalism/objectivity are penalized. Coordinated bombers all get penalized together when the article recovers. |
| Self-review inflation | `self_review_gap`: the delta between your self-review and the community average. Large gaps reduce professionalism. |
| Follow farming | `follower_prestige`: only followers with non-trivial reputation contribute. Fake accounts with rep=0 don't move the needle. |
| Share spam | `reshare_depth`: shares that nobody reshared have zero pedagogy impact. Only propagation depth counts. |

---

## Phase Plan

### Phase 0: Prerequisites — Track What We Need

**0a. Review count per article**

Already computable from `get_reviews_for_article`. Add a `review_count` field to article score output, use it as a confidence multiplier in `compute_reputation`.

**0b. Store review scores at review time (already done)**

The `Review.scores` JSON column already persists every reviewer's scores. No schema change needed for accuracy back-check.

**0c. Track "review caused edit"**

Need a new mechanism: when an author edits their article after receiving a review, attribute the edit to the review. Simplest approach: compare timestamps — if `article.last_modified > review.created_at` and the edit is within N days of the review, count it as "review influenced edit." More precise: check if the author's commit message references the review.

**0d. Share reshare tracking**

Shares already have `sharer_id` and `article_id`. To track reshare chains, add `parent_sharer_id` (nullable FK → users.id) to the Share model. When Alice shares, and Bob reshared after seeing Alice's share, Bob's share row has `parent_sharer_id = alice.id`. This builds a propagation tree.

### Phase 1: Simple Additions (no new tables)

**1a. Review count → objectivity multiplier**

In `compute_reputation`, weight each article's contribution by `log(1 + review_count)`. An article with 50 reviews contributes more to objectivity than one with 1 review.

Files: `workflow/reputation.py` only.

**1b. Self-review honesty gap**

After an article exits sedimentation, compare the author's self-review scores to the community-weighted average. The absolute delta feeds negatively into professionalism and objectivity.

Trigger: `publish_ready_articles` already has the article score and the self-review. Add a post-publish step that computes the gap and adjusts the author's reputation.

Files: `commands/workflow.py` `publish_ready_articles`, `workflow/reputation.py`.

**1c. Review variance check**

For each reviewer, compute the standard deviation of their review scores across all their reviews. Very low variance (always giving 3.0 across all dimensions) or very high variance without pattern → objectivity penalty. Moderate, discriminating variance → neutrality.

Files: `workflow/reputation.py` new function, called from `recompute_author_reputation`.

### Phase 2: Accuracy Back-Check (existing data, new computation)

**2a. Review accuracy at article publication**

When an article transitions from sedimentation → published, for each reviewer:
1. Compare their review scores to the final aggregated article score
2. Compute per-dimension deviation
3. Feed this into the reviewer's professionalism and objectivity

This is the key bidirectional feedback: your review quality affects your reputation.

Files: `commands/workflow.py` `publish_ready_articles`, new function in `workflow/reputation.py`.

**2b. Review harshness → collaboration**

Compute the average score each reviewer gives across all their reviews. If consistently low (e.g., avg < 2.5), apply a small collaboration penalty. If consistently high (avg > 4.5), apply a small professionalism penalty (too easy).

Files: `workflow/reputation.py`.

### Phase 3: Social Graph Signals (use existing tables)

**3a. Follower prestige (PageRank-like)**

A user's reputation gets a small boost from each follower weighted by that follower's reputation. Run as a periodic batch job (or incremental update on follow/unfollow).

Formula: `prestige_boost = Σ(follower.reputation.average()) / N_followers * weight`

Files: `workflow/reputation.py`, triggered from `follow_user` / `unfollow_user`.

**3b. Share reshare depth → pedagogy**

Track how deep a share chain goes. If Alice shares an article, Bob reshared it, Carol reshared from Bob → Alice gets pedagogy credit for depth > 1.

Requires Phase 0d (parent_sharer_id).

Files: `workflow/reputation.py`, `commands/shares.py`, `models.py`.

### Phase 4: Citation & Merge Signals

**4a. Citation prestige**

Being cited by high-score articles → professionalism boost. Citing well (your cited articles have high scores) → pedagogy boost. This is a PageRank variant on the citation graph.

Files: `workflow/reputation.py`, triggered when citation probabilities update.

**4b. Merge proposal outcomes**

Forks merged → collaboration boost for the proposer. Accepting good forks (fork article goes on to have high scores) → professionalism boost for the maintainer who accepted.

Files: `commands/merge.py` `accept_merge`, `workflow/reputation.py`.

---

## Dependency Order

```
Phase 0 (prerequisites) ─────────────────────────────────────────────┐
  ├─ 0a: review count (already computable)                           │
  ├─ 0b: review scores stored (already done)                         │
  ├─ 0c: review→edit tracking (new)                                  │
  └─ 0d: share parent_sharer_id (new column)                         │
                                                                     │
Phase 1 (simple, no new tables) ─────────────────────────────────┐   │
  ├─ 1a: review count → objectivity                    ← depends 0a │
  ├─ 1b: self-review gap                               ← depends 0b │
  └─ 1c: review variance                               ← depends 0b │
                                                                     │
Phase 2 (accuracy back-check) ───────────────────────────────────┐   │
  ├─ 2a: review accuracy at publish                     ← depends 0b, 1a│
  └─ 2b: review harshness                               ← depends 0b │
                                                                     │
Phase 3 (social graph) ──────────────────────────────────────────┐   │
  ├─ 3a: follower prestige                              ← depends Phase 2│
  └─ 3b: share reshare depth                            ← depends 0d │
                                                                     │
Phase 4 (citation & merge) ───────────────────────────────────────┐   │
  ├─ 4a: citation prestige                              ← depends citation system│
  └─ 4b: merge outcomes                                 ← depends Phase 2│
```

Each phase can be shipped independently. Phases 1-2 give the biggest impact (review accuracy + self-review honesty close the feedback loop).

---

## Architectural Impact: How to Keep Pure Algorithm Isolated

### Current Architecture Pattern (already good)

The codebase already follows a clean separation:

```
workflow/reputation.py        ← PURE compute (no storage/, no Session)
    compute_reputation(articles: list[dict]) → ReputationScores
    blend_reputation(existing: dict, new: ReputationScores) → ReputationScores
    get_reviewer_weight(reputation: dict | None) → float

workflow/scoring.py           ← PURE compute
    aggregate_review_scores(reviews: list[dict], weights, scopes) → dict | None

commands/workflow.py          ← ORCHESTRATOR (imports storage/db/crud_*, workflow/*)
    recompute_article_score(db, article_id)  → dict | None
    recompute_author_reputation(db, user_id) → ReputationScores
    publish_ready_articles(db)               → int
```

Pattern: **gather data from DB → call pure function → write result to DB**. The `Session` never leaks into `workflow/`.

### What Changes When New Signals Are Added

Each new signal follows the exact same pattern — a pure function in `workflow/` + data gathering in `commands/`:

```
workflow/reputation.py (PURE — no new imports needed)
├── compute_reputation(articles) → ReputationScores           [exists]
├── blend_reputation(existing, new, weight?) → ReputationScores [exists]
├── get_reviewer_weight(reputation) → float                   [exists]
│
├── compute_review_accuracy(review_scores, article_final, weight) → dict  [Phase 2]
│   Input: list of {reviewer_id, scores, is_self}, article's final score dict
│   Output: per-reviewer accuracy deltas for professionalism + objectivity
│
├── compute_self_review_gap(self_scores, community_scores) → dict  [Phase 1]
│   Input: two 5-dim score dicts
│   Output: {professionalism_delta, objectivity_delta}
│
├── compute_review_variance(all_review_scores: list[dict]) → float  [Phase 1]
│   Input: list of 5-dim score dicts from one reviewer
│   Output: variance penalty factor (0.0–1.0)
│
├── compute_follower_prestige(followers: list[dict]) → float  [Phase 3]
│   Input: [{reputation: dict}], caller pre-fetches follower reps
│   Output: prestige boost (0.0–1.0)
│
└── compute_share_depth_factor(reshare_depth: int) → float    [Phase 3]
    Input: depth of reshare chain
    Output: pedagogy boost factor


commands/workflow.py (ORCHESTRATOR — adds new DB queries)

recompute_author_reputation(db, user_id):
    # Existing:
    user = get_user(db, user_id)
    articles = get_articles_by_author(db, user_id)          # for compute_reputation

    # NEW Phase 1:
    all_reviews = get_reviews_by_reviewer(db, user_id)      # new CRUD function
    review_variance = compute_review_variance([r.scores for r in all_reviews])
    article_count = len(articles)

    # NEW Phase 2:
    inaccurate_reviews = get_reviews_accuracy(db, user_id)   # new CRUD function
    accuracy_deltas = compute_review_accuracy(...)

    # NEW Phase 3:
    follower_reps = get_follower_reputations(db, user_id)    # new CRUD function
    follower_prestige = compute_follower_prestige(follower_reps)

    # Compose:
    new_rep = compute_reputation(article_dicts, review_count_factor=...)
    new_rep = apply_review_variance(new_rep, review_variance)
    new_rep = apply_accuracy_deltas(new_rep, accuracy_deltas)
    new_rep = apply_follower_prestige(new_rep, follower_prestige)
    blended = blend_reputation(existing_rep, new_rep)
    update_user_reputation(db, user_id, blended.to_result())
```

### New Trigger Points (where to call recompute)

Current triggers:
| Event | Calls recompute? |
|-------|-----------------|
| submit_review | ✅ (recompute_article_score + recompute_author_reputation) |
| publish_article | ✅ (via publish_ready_articles) |
| rollback_article | ✅ (recompute_article_score) |
| sync_bundle | ✅ (via publish_ready_articles) |

New triggers needed:
| Event | Why | What to recompute |
|-------|-----|-------------------|
| accept_merge | Fork merged → collaboration signal for proposer | `recompute_author_reputation(proposer_id)` |
| article published (Phase 2) | Review accuracy back-check for all reviewers | `recompute_reviewer_reputations(article_id)` |
| unfollow_user | Follower prestige change | `recompute_author_reputation(unfollowed_id)` |
| add_share reshare | Share depth change | `recompute_author_reputation(original_sharer_id)` |

### Code That Changes — Summary by File

| File | Change | Phase |
|------|--------|-------|
| `workflow/reputation.py` | Add 5+ pure functions (review accuracy, variance, self-review gap, follower prestige, share depth) | 1–4 |
| `workflow/scoring.py` | No changes (already pure) | — |
| `commands/workflow.py` | Expand `recompute_author_reputation` to gather reviews_given, followers, share depth; add `recompute_reviewer_reputations` for post-publish back-check | 1–4 |
| `commands/merge.py` | Call `recompute_author_reputation(proposer_id)` after accept_merge | 4 |
| `commands/reviews.py` | Already calls recompute — no change needed | — |
| `commands/shares.py` | Call `recompute_author_reputation(sharer_id)` on reshare | 3 |
| `commands/users.py` | Call `recompute_author_reputation(unfollowed_id)` on unfollow | 3 |
| `storage/db/crud_review.py` | Add `get_reviews_by_reviewer(session, user_id)` for variance check | 1 |
| `storage/db/crud_user.py` | Add `get_follower_reputations(session, user_id)` for prestige | 3 |
| `storage/db/models.py` | Add `parent_sharer_id` to Share model (Phase 3) | 3 |
| `storage/db/engine.py` | Migration for new column | 3 |
| `config/params.py` | Add tuning knobs for each new signal weight | 1–4 |

### Key Design Rule

**No Session/ORM objects cross the `workflow/` boundary.** Every pure function takes plain Python types (dict, list, float, str). The orchestrator in `commands/` converts ORM objects to dicts before calling `workflow/` functions, and converts results back to ORM writes after. This is already the pattern in `recompute_article_score` (review ORM objects → review_dicts → `aggregate_review_scores`) — we extend it to all new signals.

### What Does NOT Change

- `workflow/scoring.py` — article score aggregation is orthogonal to reputation signals
- `policies/articles.py` — authorization rules don't depend on reputation internals
- `transport/` — HTTP layer doesn't change
- `cli/` — no user-facing changes in Phase 1-2 (Phases 3-4 may add `peerpedia reputation show`)

## Verification

1. **Unit tests** for each new `workflow/reputation.py` function with known inputs/outputs
2. **Integration tests** in `tests/test_commands.py`: publish an article with self-review gap, verify reputation adjustment
3. **Architecture tests**: ensure new functions stay in `workflow/` (pure compute, no IO)
4. **Backward compatibility**: existing tests must continue to pass — all new signals are additive, they don't remove existing behavior
5. **Manual smoke test**: `peerpedia article publish`, check author reputation changed correctly
