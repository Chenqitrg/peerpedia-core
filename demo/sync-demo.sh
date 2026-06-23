#!/usr/bin/env bash
# PeerPedia P2P sync demo — two peers exchange articles via a shared directory.
set -euo pipefail

SHARED=$(mktemp -d /tmp/peerpedia-demo-shared.XXXXXX)
A_HOME=$(mktemp -d /tmp/peerpedia-demo-A.XXXXXX)
B_HOME=$(mktemp -d /tmp/peerpedia-demo-B.XXXXXX)

cleanup() {
    rm -rf "$SHARED" "$A_HOME" "$B_HOME"
    echo "[cleanup] Removed temp directories"
}
trap cleanup EXIT

PEERPEDIA="python3 -m peerpedia_core.cli"

echo "=== PeerPedia P2P Sync Demo ==="
echo "Shared dir: $SHARED"
echo "Peer A:     $A_HOME"
echo "Peer B:     $B_HOME"

# ── Register users ──────────────────────────────────────────────────────────

echo ""
echo "── Registering users ──"
PEERPEDIA_HOME="$A_HOME" $PEERPEDIA account register --name "Alice" --json
PEERPEDIA_HOME="$B_HOME" $PEERPEDIA account register --name "Bob" --json

# ── Peer A: Create + publish ────────────────────────────────────────────────

echo ""
echo "── Peer A: Creating article ──"
A_RESULT=$(PEERPEDIA_HOME="$A_HOME" $PEERPEDIA article create \
    --title "A Note on Tensor Networks" \
    --format markdown \
    --content "# Introduction\n\nTensor networks provide a powerful framework..." \
    --user Alice \
    --publish \
    --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4" \
    --json)
A_ID=$(echo "$A_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'][:8])")
echo "Peer A article: $A_ID"

# ── Peer A: Push ────────────────────────────────────────────────────────────

echo ""
echo "── Peer A: Pushing to shared dir ──"
PEERPEDIA_HOME="$A_HOME" $PEERPEDIA sync push --path "$SHARED"

# ── Peer B: Pull ────────────────────────────────────────────────────────────

echo ""
echo "── Peer B: Pulling from shared dir ──"
PEERPEDIA_HOME="$B_HOME" $PEERPEDIA sync pull --path "$SHARED"

# ── Peer B: Verify ──────────────────────────────────────────────────────────

echo ""
echo "── Peer B: Verifying article appears ──"
B_LIST=$(PEERPEDIA_HOME="$B_HOME" $PEERPEDIA article list --json)
echo "$B_LIST" | python3 -c "
import sys, json
articles = json.load(sys.stdin)
if not articles:
    sys.exit('FAIL: No articles found on Peer B')
a = articles[0]
print(f'OK: Found article \"{a[\"title\"]}\" (status={a[\"status\"]}, id={a[\"id\"][:8]})')
"

# ── Peer B: Submit review ───────────────────────────────────────────────────

echo ""
echo "── Peer B: Submitting review ──"
PEERPEDIA_HOME="$B_HOME" $PEERPEDIA review submit "$A_ID" \
    --scores "originality=5,rigor=4,completeness=3,pedagogy=4,impact=5" \
    --comment "Well-structured argument. Section 3 could use more lemmas." \
    --user Bob

# ── Peer B: Push back ───────────────────────────────────────────────────────

echo ""
echo "── Peer B: Pushing review back ──"
PEERPEDIA_HOME="$B_HOME" $PEERPEDIA sync push --path "$SHARED"

# ── Peer A: Pull review ─────────────────────────────────────────────────────

echo ""
echo "── Peer A: Pulling review ──"
PEERPEDIA_HOME="$A_HOME" $PEERPEDIA sync pull --path "$SHARED"

# ── Peer A: Verify review ───────────────────────────────────────────────────

echo ""
echo "── Peer A: Verifying review appears ──"
A_REVIEWS=$(PEERPEDIA_HOME="$A_HOME" $PEERPEDIA review list "$A_ID" --json)
echo "$A_REVIEWS" | python3 -c "
import sys, json
reviews = json.load(sys.stdin)
if not reviews:
    sys.exit('FAIL: No reviews found')
r = reviews[0]
print(f'OK: Found review with scores {r[\"scores\"]}')
"

echo ""
echo "=== Demo complete: 2-peer sync round-trip verified ==="
