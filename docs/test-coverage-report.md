# Test Coverage Report

**Date:** 2026-06-25
**Branch:** main
**Tool:** pytest 9.1.0 + pytest-cov 7.1.0
**Python:** 3.11+

## Overview

| Metric | Value |
|--------|-------|
| **Line coverage** | **69%** (4693 statements) |
| **Test files** | 39 |
| **Test cases** | 570 (all passing) |
| **100% coverage files** | 32 |
| **Below 50% coverage** | 15 (transport + CLI handlers + REPL) |

## By Package

```
config           ██████████ 100%
types            ██████████ 100%
workflow         ██████████  99%
social           ██████████  96%
storage/db/crud  █████████░  92%  (crud_merge, crud_review edges)
storage/db/model █████████░  98%
storage          ████████░░  85%  (git_backend merge error paths)
policies         ████████░░  88%  (defensive branches)
commands         ████████░░  85%  (network-dependent paths)
cli/display      ██████░░░░  62%  (display_diff only)
cli/handlers     ███░░░░░░░  43%  (social push paths, article lifecycle)
transport/routes ██████░░░░  62%  (TestClient coverage)
transport/auth   ████████░░  80%  (sign + roundtrip)
transport/client ███░░░░░░░  32%  (needs live server for success paths)
repl             ███░░░░░░░  23%  (interactive mode)
```

## 100% Coverage Files (32)

- `config/paths.py`, `config/git.py`, `config/params.py`
- `types/scores.py`
- `exceptions.py`, `frontmatter.py`
- `policies/articles.py` (88% → now exercise most branches)
- `workflow/scoring.py`, `workflow/state.py`
- `storage/db/crud_alias.py`, `storage/db/crud_bookmark.py`
- `storage/db/crud_citation.py`, `storage/db/crud_maintainer.py`
- `storage/db/crud_notification.py`, `storage/db/crud_share.py`
- `storage/db/crud_user.py` (100%), `storage/db/session_utils.py`
- `transport/shared.py`, `transport/middleware/logging.py`
- `social/exchange.py` (96%)
- Plus 10+ more

## Recent Improvements

| Area | Before | After | Tests Added |
|------|--------|-------|-------------|
| crud_alias.py | 23% | 100% | 6 |
| crud_share.py | 32% | 100% | 8 |
| crud_user.py | 80% | 100% | 5 |
| crud_notification.py | — | 100% | 17 |
| workflow/state.py | 83% | 100% | 5 |
| transport/routes | 39% | 62% | 34 |
| CLI handlers | 0% | 43% | 23 |
| Policies | 85% | 88% | 5 |
| Spec (user journeys) | — | — | 6 |

## Remaining Gaps

- `transport/http_client.py` (32%): success paths need live server fixture
- `cli/handlers/social.py` (20%): P2P push paths need PEERPEDIA_SERVER
- `cli/handlers/articles.py` (13%): full article lifecycle via CLI
- `repl.py` (23%): interactive REPL mode
