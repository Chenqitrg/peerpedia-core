# Review Format Design

## Git Repo Structure

Each article is an independent git repository:

```
~/.peerpedia/articles/{article_id}/
├── .git/
├── article.md                  # Article body + metadata (YAML frontmatter)
└── reviews/
    ├── {reviewer_a}.md         # Reviewer A's review + author discussion thread
    ├── {reviewer_b}.md         # Reviewer B's review + author discussion thread
    └── {author_id}.md          # Author self-review (same format as other reviews)
```

## Article File Format (`article.md`)

```markdown
---
title: A Note on Tensor Networks
abstract: Tensor networks provide a powerful framework for...
keywords: [tensor networks, quantum physics, entanglement]
categories: [physics, mathematics]
---

# Introduction

正文内容...
```

- **YAML frontmatter** stores title, abstract, keywords, categories — the metadata that changes with edits
- **Markdown body** is the article content
- DB caches these fields for querying; git is the SOT

## Review File Format (`reviews/{user_id}.md`)

```markdown
---
originality: 4
rigor: 3
completeness: 4
pedagogy: 3
impact: 5
---

### Feynman (2024-03-15T10:30:00Z)

The argument structure is solid. Section 3 could use more lemmas.

### Einstein (2024-03-15T14:20:00Z)

Thanks for the feedback. Lemmas added — see commit abc123.
```

**Rules:**
- **YAML frontmatter** stores the five-dimension scores. Parsed by Python `yaml` library.
- **Markdown body** is the conversation thread. Each message is `### DisplayName (ISO8601-Timestamp)` followed by content.
- **One file per reviewer.** Multi-round discussions append to the same file.
- **Self-review is just another review** — stored as `reviews/{author_id}.md`, identical format.

## Changes from Current Implementation

| Aspect | Current | New |
|--------|---------|-----|
| Scores storage | `reviews/{id}/scores.json` (separate JSON file) | YAML frontmatter in `reviews/{id}.md` |
| Thread storage | `reviews/{id}/thread.md` (separate Markdown file) | Same `.md` file, after frontmatter |
| Self-review | DB only, not written to git | `reviews/{author_id}.md`, git-first |
| Files per reviewer | 2 (`scores.json` + `thread.md`) | 1 (`{reviewer_id}.md`) |
| Directory per reviewer | `reviews/{id}/` subdirectory | Flat `reviews/` directory |

## Code Changes Required

### Git → DB alignment for article metadata
1. **`create_article_with_content` in commands.py**: Write `article.md` with YAML frontmatter (title, abstract, keywords, categories)
2. **`update_article_content` in commands.py**: Update YAML frontmatter when metadata changes
3. **DB metadata fields become caches**: After reading from git, sync to DB for queries

### Review format migration
4. **`_write_review_to_git` in commands.py**: Write `reviews/{id}.md` with YAML frontmatter instead of `scores.json` + `thread.md`
5. **`create_article_with_content` in commands.py**: Self-review writes `reviews/{author_id}.md` to git before commit
6. **`Review` model in models.py**: `thread` field becomes optional cache; real content lives in git
7. **`crud_review.py`**: `upsert_review` parses YAML frontmatter from git file to populate DB cache
8. **`init_article_repo` in git_backend.py**: Already creates `reviews/` directory — no change needed
9. **Data migration**: Convert existing `scores.json` + `thread.md` to the new format

## Non-Goals

- Rendering logic for displaying review threads is out of scope — this spec only covers storage format
- The `Review` DB model's exact caching schema is not changed in this spec
