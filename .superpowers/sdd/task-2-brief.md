### Task 2: Iron Rules Block

**Files:**
- Modify: `skills/code-refactoring/SKILL.md` (append after When to Use section)

**Produces:** 10 iron rules in ALL CAPS code block with anti-rationalization preamble.

- [ ] **Step 1: Append the Iron Rules section**

```markdown
## Iron Rules

These are non-negotiable. Violating any of them means the refactoring is wrong.

```
NO MOVING CODE WITHOUT UNDERSTANDING ITS SIBLINGS FIRST
NO SPLITTING WITHOUT NAMING THE ORCHESTRATOR
NO INLINE IMPORTS SURVIVE WITHOUT JUSTIFICATION
NO FALLBACK — every step fails LOUD with an actionable error message
NO REFACTORING WITHOUT THREE PASSES — Map, Intent, Diagnose
NO AWKWARD FUNCTION AS ARCHITECTURE CENTER — find natural behaviors
NO INCONSISTENT NAMES IN THE SAME DOMAIN — siblings share a verb convention
NO SINGLE-PASS DIAGNOSIS — 8 lenses, one question each, every lens reports
NO INLINE VALUES — string building goes to dedicated formatters, magic literals go to constants
NO REINVENTING — search the codebase before extracting; generalize repeated patterns, don't duplicate them
```

**The letter of these rules IS the spirit.** If you find yourself thinking "this
is a special case" — it's not. The rules exist because that exact rationalization
has been wrong every time.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/chenqimeng/.claude/plugins/cache/claude-plugins-official/superpowers/6.0.3
git add skills/code-refactoring/SKILL.md
git commit -m "feat(code-refactoring): add 10 iron rules

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

