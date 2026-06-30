# Code Refactoring Skill — Design Spec

## Overview

A principles-driven code refactoring skill for the superpowers plugin system.
Teaches the model code aesthetics principles first, then applies a 7-step process
to systematically diagnose and fix code structure. Mandatory steps ensure critical
issues aren't missed; conditional steps use explicit decision gates to avoid
over-refactoring.

**Target audience**: Any Python project. The skill is principles-driven, not
project-specific — it teaches the model *how* to think about code structure,
then uses the project's own conventions (CLAUDE.md, existing naming patterns)
as the standard.

---

## Trigger Conditions

Invoke when the user expresses dissatisfaction with code quality:

- "这个文件太长了" / "this file is too long"
- "这个模块很乱" / "these functions are messy"
- "重构一下" / "refactor this" / "clean up"
- "代码需要整理" / "organize the code"
- User points at a file/module and implies structural problems
- Any request mentioning "refactor", "clean up", "organize", "restructure"

---

## Iron Rules (8)

```
NO MOVING CODE WITHOUT UNDERSTANDING ITS SIBLINGS FIRST
NO SPLITTING WITHOUT NAMING THE ORCHESTRATOR
NO INLINE IMPORTS SURVIVE WITHOUT JUSTIFICATION
NO FALLBACK — every step fails LOUD with an actionable error message
NO REFACTORING WITHOUT THREE PASSES — Map, Intent, Diagnose
NO AWKWARD FUNCTION AS ARCHITECTURE CENTER — find natural behaviors
NO INCONSISTENT NAMES IN THE SAME DOMAIN — siblings share a verb convention
NO SINGLE-PASS DIAGNOSIS — six lenses, one question each, every lens reports
```

---

## Step 0: Three-Pass Reading (MANDATORY)

### Pass 1 — Map (Structure Mapping)

**Question**: What is in this module?

**Read method**:
- Read the import block (first 40 lines) of every file in scope
- Read function/class signatures only — do NOT read implementations
- Build an import dependency graph: which file imports what from where

**Deliverable**: Import dependency graph + function/class signature inventory

**Forbidden**:
- Grep for a symbol and only read those 3 lines
- Skip the import block — it tells you the dependency direction
- Start reading implementations (that's Pass 2)

**Success criterion**: Can draw the dependency arrow direction between every pair of modules.

---

### Pass 2 — Intent (Purpose Understanding)

**Question**: Why does each function exist? Who are its siblings?

**Read method**:
- Read the full function body, from `def` to the last `return` (or end of function)
- For each function, answer three questions:
  1. **What does it do?** (one-sentence behavior description)
  2. **Is its behavior natural in the domain?** (is it "publish an article" or "publish an article and also update a counter and clean up temp files"?)
  3. **Who are its siblings?** (which other functions belong to the same domain set?)

**Deliverable**: Per-function annotation: (1) behavior description, (2) naturalness judgment, (3) sibling assignment

**Forbidden**:
- Judge a function's purpose from its first 5 lines — read to the end
- Skip "boring" helper functions — they're often the ones in the wrong place
- Assume the function name accurately describes its behavior — verify

**Anti-pattern marker**:
- "Awkward function" — behavior logic is unnatural, does 1.5 things, name and implementation don't match
- Mark these as **priority split targets** — do not let them become architecture centers

**Success criterion**: Every function can answer "who are its siblings?"

---

### Pass 3 — Diagnose (6 Parallel Subagents)

**Question**: What is wrong, specifically?

**Method**: Dispatch 6 subagents in parallel. Each subagent receives the same code context + one lens question. Each subagent MUST produce a structured findings list or explicitly declare "no findings."

#### Lens A — Fallback Lens
```
Question: Where is there silent fallback?
Look for: None → skip, except → pass, default parameters masking errors,
          try/except without re-raise, .get() with defaults that hide missing data
Deliverable: fallback violation list, or "no findings"
```

#### Lens B — Naming Lens
```
Question: Are sibling functions named consistently? Do names match behavior?
Look for: get_/fetch_/retrieve_ mixing in the same domain, names that lie about behavior,
          private (_) vs public naming inconsistency
Deliverable: naming violation list, or "no findings"
```

#### Lens C — Dependency Lens
```
Question: Are import directions correct? Any cross-package private imports? Circular refs?
Look for: layer violations (storage → core, server → transport/http),
          _internal module imports from another package,
          potential circular imports
Deliverable: dependency violation list, or "no findings"
```

#### Lens D — Structure Lens
```
Question: Does each function belong in the correct module? Any awkward functions? Any that need splitting?
Look for: functions in wrong layer, functions separated from siblings,
          functions >30 lines, functions doing 2+ unrelated things,
          guard/action mixing
Deliverable: structure violation list, or "no findings"
```

#### Lens E — Dead Code Lens
```
Question: What is unreferenced?
Look for: functions/classes/variables never called, imports never used,
          code paths that can never execute
Deliverable: dead code list, or "no findings"
```

#### Lens F — Type Safety Lens
```
Question: Any bare types? Union parameters? Callable[..., X]?
Look for: bare dict/list/tuple, str | set[str] on parameters,
          Callable[..., X] instead of full signature, Any outside serialization boundaries
Deliverable: type violation list, or "no findings"
```

**Rules**:
- Each subagent is independent — contexts don't contaminate
- Each MUST produce output or explicitly declare "no findings"
- Main agent merges 6 reports → deduplicates → sorts by severity → produces unified violation list
- Lens F (Type Safety) findings are annotation-level fixes — resolve them inline during Steps 1-3, no separate step needed

**Why parallel subagents**: AI attention is linear — with 6 questions competing in one context, the model notices the most salient and ignores the rest. Six independent subagents each carry one question through the full code, ensuring nothing is missed.

```
AI default (linear):    Read → notice most salient → ignore rest
                         ↑ 6 questions fighting for one attention span

Single-agent multi-pass: A done → B done → C done → ...
                         ↑ serial, each question asked, but slow

Parallel subagents:      A ─┐
                         B ─┤
                         C ─┼─ run simultaneously → merge
                         D ─┤
                         E ─┤
                         F ─┘
                         ↑ independent contexts, truly parallel
```

**Success criterion**: Every violation in the unified list can be traced to specific evidence from Pass 1 or Pass 2.

---

## Step 1: Split Functions (CONDITIONAL)

**Decision gate** — split if ANY of these are true:

| Condition | How to detect |
|---|---|
| Function >30 lines | Count logic lines from `def` to last statement (exclude docstrings, blank lines, decorators) |
| Does 2+ unrelated things | Pass 2 behavior description contains "and also" |
| Name can't summarize behavior | "What does this function do?" → need 2+ sentences |
| Mixes guard and action | Checks conditions AND transforms data — violates aesthetics principle |
| Awkward function | Pass 2 marked it as "awkward" |

**Skip if**: The function is a naturally complete behavior. Even if long, it doesn't need splitting — hand to Step 4 for phase comments.

**Must deliver**: An orchestrator function name — after splitting, which function is the caller/entry point?

**Red flags**:
- Splitting every long function mechanically without considering natural behavior boundaries
- Creating functions named `_helper_1`, `_helper_2`

---

## Step 2: Group Similar Functions + Unify Names (CONDITIONAL)

**Decision gate** — group if ANY of these are true:

| Condition | How to detect |
|---|---|
| 3+ functions do similar things but live in different files | Pass 2 sibling assignments point across files |
| Two functions have >50% duplicate logic | Visual comparison |
| A domain set is split across multiple files | e.g. "SSH signing triad" across 3 files |
| Sibling functions have inconsistent names | `get_`/`fetch_`/`retrieve_` mixed in same domain |

**Naming unification rules**:
1. Find the most frequent naming pattern in the domain set → use as standard
2. Rename the rest to match
3. If no clear majority (50/50 split) → prefer the project's existing conventions (e.g. PeerPedia's `fetch_`/`push_`/`discover_`/`reconcile_`)
4. If no project convention exists → pick the simplest, document the decision

**Skip if**: Siblings are already co-located and names are consistent.

**Red flags**:
- Moving functions without checking if the target module's layer is correct
- Renaming without updating all call sites

---

## Step 3: Module Correctness Review (MANDATORY)

Cross-reference Pass 1's dependency graph against Pass 2's sibling assignments:

- Audit every function: is it in the right module?
- Layer violations → move (e.g. `core/` function that is pure compute → `compute/`)
- Sibling separation → move (function A's siblings are in `storage/git/` but A lives in `core/`)
- Wrong-direction imports → mark for Step 6

**Red flags**:
- Moving a function that "sort of works here" without checking where its siblings are
- Resolving layer violations by adding an import allowance instead of moving the function

---

## Step 4: Phase Comments for Unsplit Functions (CONDITIONAL)

For functions that Step 1 decided NOT to split, annotate internal logic phases:

```python
def _process_sink_article(db, article):
    # ── Sink timer check ──
    if article.sink_start is None: return None
    ...
    # ── Count approvals ──
    approval_count = _count_approving_reviews(db, article.id, authors)
    # ── Decide disposition ──
    decision = _decide_sink_disposition(article, approval_count)
    # ── Git: write status marker ──
    if decision != "extended" and has_repo:
        commit_status_marker(rp, decision)
    # ── DB: update status + score ──
    update_article_status(db, article.id, decision)
```

**Skip if**: The function has only one logical phase (no phases to label).

**Red flags**:
- Adding phase comments to a function that should actually be split
- Phase labels that are too vague to be useful ("── Do stuff ──")

---

## Step 5: De-inline Imports (MANDATORY)

- Scan for all `import` statements NOT at module top level
- Move each to the top of the file
- If moving to the top creates a circular import → **do NOT use `TYPE_CHECKING` as a workaround**
- Instead: mark the function as misplaced, route to Step 6

**Red flags**:
- Using `TYPE_CHECKING` to paper over circular imports
- Hiding imports inside functions to avoid thinking about architecture

---

## Step 6: Architecture Clarity (MANDATORY)

Verify every cross-module reference follows correct dependency direction:

| Reference direction | Verdict |
|---|---|
| `core/` → `transport/` | ✓ Correct |
| `core/` → `storage/` | ✓ Correct |
| `server/` → `core/` | ✓ Correct |
| `server/` → `transport/http/` | ✗ Violation — function doesn't belong in `server/` |
| `storage/` → `core/` | ✗ Violation — layer inversion |
| Any → `_internal.py` in another package | ✗ Cross-package private import |

**For violations**: Move the function, don't add a bypass.

For projects without an explicit layer architecture in CLAUDE.md: infer the dependency direction from existing import patterns.

**Red flags**:
- Convincing yourself "this one import is fine" — it's never just one
- Moving the function to a "utils.py" instead of finding its real home

---

## Step 7: Remove Dead Code (MANDATORY)

After Steps 1-6 are complete, scan for:

- Functions/classes/variables no longer referenced anywhere
- Imports that are no longer used
- Empty shells left behind after moving/splitting functions
- Code paths rendered unreachable by the refactoring

**For each deletion**: State *why* it's dead code (what made it unreferenced).

**Red flags**:
- Deleting code you "think" is unused without grepping for references
- Keeping dead code "just in case"

---

## Error Format (Global)

Every failure must produce:

```
✗ Attempted:  [concrete action, e.g. "Move _normalize_keys from core/guards.py to types/scores.py"]
✗ Blocked by: [concrete blocker, e.g. "Circular import: types/scores.py already imports core/guards.py"]
→ Investigate: [actionable direction, e.g. "Check if _normalize_keys belongs in compute/ instead,
               or if core/guards.py's import of types/scores.py points the wrong way"]
```

No generic error messages. "It didn't work" is not acceptable.

---

## Rationalization Table

| Excuse | Reality |
|---|---|
| "This function is fine here" | If it's separated from its siblings, it's not fine. |
| "It's only one import" | Layer violations are never "only one." |
| "I'll add a comment instead of splitting" | Comments don't fix structural problems. |
| "TYPE_CHECKING fixes the circular import" | TYPE_CHECKING hides the symptom; the architecture is wrong. |
| "This function is too simple to move" | Simple functions in the wrong place compound into chaos. |
| "I read the first 30 lines, I know what it does" | You read 30 lines. You don't know. Read the whole thing. |
| "The names are close enough" | Inconsistent names in the same domain confuse every future reader. |
| "This fallback is harmless" | Silent fallback is never harmless — it hides bugs. |
| "I skimmed the file, I have a good sense of it" | AI attention is linear. You noticed one thing. Run all 6 lenses. |
| "This function is only 5 lines, no need to check" | A 5-line function doing 2 unrelated things is worse than a 30-line function doing 1. |

---

## Red Flag Thoughts

These thoughts mean STOP — you're about to violate an iron rule:

- "Let me just grep for this function" → Read the full import block and function body. No grep-jumping.
- "I can split this later" → You won't. Split it now or write the phase comment now.
- "The circular import can be resolved with TYPE_CHECKING" → The function is misplaced. Find its real home.
- "I'll move this one function, no need to check siblings" → Iron rule #1. Find siblings first.
- "This error is obscure, I'll just catch it and move on" → Iron rule #4. Fail LOUD with the error format.
- "This function is weird but it works" → Iron rule #6. Awkward functions must not be architecture centers.
- "I found the main issues, no need to run all 6 lenses" → Iron rule #8. Every lens reports.
- "This name is different but it's clear enough" → Iron rule #7. Siblings share a verb convention.

---

## Quick Reference

| Step | Name | Required | Key Decision |
|---|---|---|---|
| 0 | Three-Pass Reading (Map → Intent → 6-Lens Diagnose) | **MANDATORY** | Foundation for all later steps |
| 1 | Split Functions | Conditional | Split if >30 lines OR 2+ behaviors OR awkward OR guard+action mixed |
| 2 | Group + Unify Names | Conditional | Group if 3+ scattered siblings OR >50% duplicate OR naming inconsistency |
| 3 | Module Correctness Review | **MANDATORY** | Every function checked against layer rules and sibling assignment |
| 4 | Phase Comments | Conditional | Annotate if unsplit function has 2+ logical phases |
| 5 | De-inline Imports | **MANDATORY** | Move to top; circular import → function is misplaced → Step 6 |
| 6 | Architecture Clarity | **MANDATORY** | Verify all cross-module reference directions |
| 7 | Remove Dead Code | **MANDATORY** | Delete unreferenced code; state why it's dead |

---

## Scope Expansion

The skill starts from the user's target (a file or module) and auto-expands:

1. Read target → identify sibling functions in other files
2. If siblings are found outside the target → expand scope to include them
3. If moving a function to a new module → check that module's siblings too
4. Expansion stops when no more sibling relationships are found

The user is notified of scope expansion: "Found 3 sibling functions in `storage/git/trailers.py` — expanding scope to include them."

---

## Integration with Existing Skills

- **REQUIRED BACKGROUND**: This skill assumes the model has basic code reading competence. If the project has a CLAUDE.md, read it first to understand project-specific conventions.
- **BEFORE IMPLEMENTING**: Use `superpowers:writing-plans` to create an implementation plan from this spec.
- **AFTER COMPLETION**: Use `superpowers:verification-before-completion` to run tests and verify the refactoring didn't break anything.
