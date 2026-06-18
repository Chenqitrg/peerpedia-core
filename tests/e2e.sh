#!/bin/bash
# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
#
# PeerPedia end-to-end specification tests.
# Treats the system as a black box — only CLI commands and their output.
#
# Usage: PEERPEDIA=.venv/bin/peerpedia bash tests/e2e.sh

set -euo pipefail

PEERPEDIA="${PEERPEDIA:-peerpedia}"
PASS=0; FAIL=0
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

export PEERPEDIA_HOME="$TMPDIR/home"
mkdir -p "$PEERPEDIA_HOME/articles"

_run()  { HOME="$PEERPEDIA_HOME" "$PEERPEDIA" "$@" 2>&1 || true; }
_run_j() { HOME="$PEERPEDIA_HOME" "$PEERPEDIA" "$@" --json 2>&1 || true; }

_pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
_fail() { FAIL=$((FAIL + 1)); echo "  ✗ $1 (expected: $2)"; }

_assert() {
    if echo "$1" | grep -q "$2"; then _pass "$3"
    else _fail "$3" "contains '$2'"; fi
}
_id() { echo "$1" | grep -o '"id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*: *"//;s/"$//'; }

# ═════════════════════════════════════════════════════════════════════════
# Flow 1: Registration & Identity
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 1: Registration ==="

OUT=$(_run account register --name Alice)
_assert "$OUT" "Registered" "F1.1 register creates account"

OUT=$(_run account register --name Bob)
_assert "$OUT" "Registered" "F1.1 register second account"

# ═════════════════════════════════════════════════════════════════════════
# Flow 2: Article create, edit, show, list, delete
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 2: Article Lifecycle ==="

OUT=$(_run article create --title "Tensor Networks 101" --format markdown \
    --content "# Introduction\n\nTensor networks are powerful." --user Alice)
_assert "$OUT" "Tensor Networks 101" "F2.1 create article"
_assert "$OUT" "draft"              "F2.1 status is draft"
ART_ID=$(_id "$(_run_j article create --title "TN" --format markdown --content x --user Alice)")

# Show
OUT=$(_run article show "$ART_ID" --user Alice)
_assert "$OUT" "TN" "F2.4 show article"

# List
OUT=$(_run article list --user Alice)
_assert "$OUT" "TN" "F2.5 list articles"

# Edit
OUT=$(_run article edit "$ART_ID" --content "# Updated" --user Alice)
_assert "$OUT" "Updated" "F2.3 edit article"

OUT=$(_run article show "$ART_ID" --user Alice)
_assert "$OUT" "Updated" "F2.3 edited content visible"

# Delete
OUT=$(_run article delete "$ART_ID" --force --user Alice)
_assert "$OUT" "Deleted" "F2.6 delete article"
OUT=$(_run article show "$ART_ID" --user Alice)
_assert "$OUT" "not found" "F2.6 deleted article gone"

# ═════════════════════════════════════════════════════════════════════════
# Flow 3: Publish to sedimentation pool
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 3: Publish ==="

# Create + publish in one step
OUT=$(_run article create --title "Paper for Pool" --format markdown \
    --content "# Pool test" --user Alice --publish \
    --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4")
_assert "$OUT" "sedimentation" "F3.1 create+publish enters sedimentation"
POOL_ID=$(_id "$(_run_j article create --title "P2" --format markdown --content x --user Alice)")

# Publish existing draft
OUT=$(_run article publish "$POOL_ID" \
    --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4" \
    --user Alice)
_assert "$OUT" "Published" "F3.1 publish draft to pool"
OUT=$(_run article show "$POOL_ID" --user Alice)
_assert "$OUT" "sedimentation" "F3.1 status becomes sedimentation"

# ═════════════════════════════════════════════════════════════════════════
# Flow 4: Review system
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 4: Review ==="

REV_ID=$POOL_ID
OUT=$(_run review submit "$REV_ID" \
    --scores "originality=5,rigor=4,completeness=3,pedagogy=4,impact=5" \
    --comment "Well-structured argument." --user Bob)
_assert "$OUT" "Review submitted" "F4.1 submit review"

OUT=$(_run review list "$REV_ID" --user Alice)
_assert "$OUT" "5" "F4.2 review scores visible"

# ═════════════════════════════════════════════════════════════════════════
# Flow 5: Fork & Merge
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 5: Fork & Merge ==="

# Need published article for fork. Create+publish via Python to get published status.
FORK_SRC=$(.venv/bin/python -c "
from peerpedia_core.storage.db.engine import get_engine, get_session, init_db
from peerpedia_core.storage.db.crud_article import create_article, update_article_status
from peerpedia_core.storage.db.crud_user import create_user as cu
import bcrypt, uuid
db_url = 'sqlite:///$PEERPEDIA_HOME/peerpedia.db'
e = get_engine(db_url); init_db(e); s = get_session(e)
uid = str(uuid.uuid4())
cu(s, username='charlie', password_hash=bcrypt.hashpw(b'x', bcrypt.gensalt()).decode(), name='Charlie', anonymous_name='anon_c')
a = create_article(s, id=str(uuid.uuid4()), title='Forkable', authors=[uid], status='published')
s.commit()
print(a.id)
" 2>&1)
echo "  Fork source: $FORK_SRC"

# Register Charlie so the CLI can resolve them
OUT=$(_run account register --name Charlie 2>&1)
_assert "$OUT" "Registered" "F5.0 register Charlie"

OUT=$(_run fork "$FORK_SRC" --user Bob)
_assert "$OUT" "Forked" "F5.1 fork article"
FORK_ID=$(_id "$(_run_j fork "$FORK_SRC" --user Bob)")

[ -z "$FORK_ID" ] && FORK_ID="unknown"

# ═════════════════════════════════════════════════════════════════════════
# Flow 6: Bookmarks
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 6: Bookmarks ==="

OUT=$(_run bookmark add "$FORK_SRC" --user Bob)
_assert "$OUT" "Bookmarked" "F6.1 add bookmark"

OUT=$(_run bookmark list --user Bob)
_assert "$OUT" "$FORK_SRC" "F6.2 bookmark list shows article"

# ═════════════════════════════════════════════════════════════════════════
# Flow 8: Error handling
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 8: Error Handling ==="

OUT=$(_run article create --title "" --format markdown --content "x" --user Alice)
_assert "$OUT" "Title is required" "E8.1 empty title rejected"

OUT=$(_run article create --title "X" --format markdown --content "x" --user Nobody)
_assert "$OUT" "not found" "E8.2 nonexistent user rejected"

OUT=$(_run article edit "$POOL_ID" --content "# Hacked" --user Bob)
_assert "$OUT" "not authorized\|NotAuthorized" "E8.3 non-author edit rejected"

OUT=$(_run fork "$FORK_SRC" --user Bob 2>&1 || true)
# Second fork of same article should fail
_assert "$OUT" "Already forked\|ConflictError" "E8.4 duplicate fork rejected"

# ═════════════════════════════════════════════════════════════════════════
# Flow 7: Sync
# ═════════════════════════════════════════════════════════════════════════

echo "=== Flow 7: Sync ==="

OUT=$(_run sync status)
_assert "$OUT" "offline\|online" "F7.1 sync status shows server state"

# ═════════════════════════════════════════════════════════════════════════
# Results
# ═════════════════════════════════════════════════════════════════════════

echo ""
echo "═══════════════════════════════════════"
echo "  Passed: $PASS  Failed: $FAIL"
echo "═══════════════════════════════════════"

[ "$FAIL" -eq 0 ] || exit 1
