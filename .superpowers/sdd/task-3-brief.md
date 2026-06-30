### Task 3: Step 0 — Three-Pass Reading (Map + Intent)

**Files:**
- Modify: `skills/code-refactoring/SKILL.md` (append after Iron Rules)

**Produces:** Pass 1 (Map) and Pass 2 (Intent) with read rules, deliverables, forbidden actions, success criteria.

- [ ] **Step 1: Write Step 0 header + Pass 1 (Map)**

```markdown
## Step 0: Three-Pass Reading (MANDATORY)

Do NOT skip to splitting. Do NOT grep-jump. You read three times, each with a
different question. Every pass has a written deliverable. No deliverable = pass not done.

### Pass 1 — Map (Structure Mapping)

**Question**: What is in this module?

**Read method**:
1. Read the import block (first 40 lines) of EVERY file in scope — do not skip any
2. Read function/class signatures only — do NOT read implementations
3. Build an import dependency graph: which file imports what from where

**Deliverable**: Written import dependency graph + function/class signature inventory.
A mental note doesn't count. Write it down.

**Forbidden**:
- Grep for a symbol and only read those 3 lines → GREP-JUMP. Read the full import block.
- Skip the import block because "I already know what it imports" → you don't.
- Start reading implementations → that's Pass 2. Stay disciplined.

**Success criterion**: You can draw the dependency arrow direction between every
pair of modules. If you can't, you didn't finish Pass 1.
```

- [ ] **Step 2: Write Pass 2 (Intent)**

```markdown
### Pass 2 — Intent (Purpose Understanding)

**Question**: Why does each function exist? Who are its siblings?

**Read method**:
1. Read the FULL function body — from `def` to the last `return` (or end of function)
2. For each function, answer THREE questions:
   a. **What does it do?** (one-sentence behavior description)
   b. **Is its behavior natural in the domain?**
      - "Publish an article" → natural
      - "Publish an article AND update a counter AND clean up temp files" → AWKWARD
   c. **Who are its siblings?** (which other functions belong to the same domain set?)

**Deliverable**: Per-function annotation: (a) behavior description, (b) naturalness
judgment, (c) sibling assignment. Write one line per function.

**Forbidden**:
- Judge a function from its first 5 lines → read to the end. Always.
- Skip "boring" helper functions → they're often the ones in the wrong place
- Assume the function name is accurate → verify against the implementation

**Awkward function marker**: If the function's name says one thing but the
implementation does 1.5+ things, mark it `[AWKWARD]`. These become priority
split targets in Step 1. Never let an awkward function remain an architecture
center.

**Success criterion**: Every function can answer "who are its siblings?" without
hesitation. If you hesitate on any function, re-read it.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/chenqimeng/.claude/plugins/cache/claude-plugins-official/superpowers/6.0.3
git add skills/code-refactoring/SKILL.md
git commit -m "feat(code-refactoring): add Step 0 Pass 1-2 — Map and Intent

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

