# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for git backend — article version control."""

import tempfile
from pathlib import Path

import pytest

from tests.conftest import commit_article_signed


@pytest.fixture
def articles_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def repo(articles_dir):
    """An initialized article repo with one commit."""
    from peerpedia_core.storage.git_backend import commit_article, init_article_repo

    rp = init_article_repo(articles_dir / "test-article")
    # write initial content
    (rp / "article.md").write_text("# Test\n\nHello world.\n")
    commit_article_signed(rp, "initial commit", "Test Author", "test@test.com")
    return rp


class TestInitAndCommit:
    def test_init_creates_git_dir(self, articles_dir):
        from peerpedia_core.storage.git_backend import init_article_repo

        rp = init_article_repo(articles_dir / "test-1")
        assert (rp / ".git").is_dir()
        assert rp.name == "test-1"

    def test_commit_returns_hash(self, articles_dir):
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        rp = init_article_repo(articles_dir / "test-2")
        (rp / "article.md").write_text("content")
        h = commit_article_signed(rp, "add notes", "Author", "a@b.com")
        assert len(h) == 40  # full SHA hash

    def test_commit_updates_file(self, articles_dir):
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        rp = init_article_repo(articles_dir / "test-3")
        f = rp / "article.md"
        f.write_text("v1")
        commit_article_signed(rp, "v1", "A", "a@b.com")
        f.write_text("v2")
        commit_article_signed(rp, "v2", "A", "a@b.com")
        # file has latest content
        assert f.read_text() == "v2"

    def test_commit_initial_on_empty_repo(self, articles_dir):
        """commit_article on a repo with only the init commit creates a second commit."""
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        rp = init_article_repo(articles_dir / "test-init-empty")
        (rp / "article.md").write_text("content")
        h = commit_article_signed(rp, "initial content", "A", "a@b.com")
        assert len(h) == 40


class TestHistory:
    def test_history_returns_commits(self, repo):
        from peerpedia_core.storage.git_backend import get_commit_history

        history = get_commit_history(repo)
        assert len(history) >= 1
        assert history[0]["hash"] is not None
        assert "message" in history[0]
        assert "author" in history[0]

    def test_history_order_is_newest_first(self, articles_dir):
        from peerpedia_core.storage.git_backend import (
            commit_article,
            get_commit_history,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "test-order")
        (rp / "article.md").write_text("v1")
        commit_article_signed(rp, "first", "A", "a@b.com")
        (rp / "article.md").write_text("v2")
        commit_article_signed(rp, "second", "A", "a@b.com")
        history = get_commit_history(rp)
        assert len(history) >= 2
        assert history[0]["message"].startswith("second")
        assert history[1]["message"].startswith("first")

    def test_history_empty_repo_raises(self, articles_dir):
        """get_commit_history on a repo with no commits raises ValueError."""
        from peerpedia_core.storage.git_backend import get_commit_history

        rp = articles_dir / "test-empty-history"
        rp.mkdir(parents=True, exist_ok=True)
        import git

        git.Repo.init(rp)
        with pytest.raises(ValueError, match="no commits"):
            get_commit_history(rp)


class TestDiff:
    def test_diff_returns_text(self, articles_dir):
        from peerpedia_core.storage.git_backend import (
            commit_article,
            get_commit_history,
            get_diff_between,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "test-diff-text")
        (rp / "article.md").write_text("line1\n")
        commit_article_signed(rp, "first", "A", "a@b.com")
        (rp / "article.md").write_text("line1\nline2\n")
        commit_article_signed(rp, "second", "A", "a@b.com")
        history = get_commit_history(rp)
        result = get_diff_between(rp, history[1]["hash"], history[0]["hash"])
        assert "diff_text" in result
        assert result["diff_text"]
        assert "files" in result
        assert "stats" in result

    def test_diff_between_two_commits(self, articles_dir):
        from peerpedia_core.storage.git_backend import (
            commit_article,
            get_commit_history,
            get_diff_between,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "test-diff2")
        (rp / "article.md").write_text("line1\n")
        commit_article_signed(rp, "first", "A", "a@b.com")
        (rp / "article.md").write_text("line1\nline2\n")
        commit_article_signed(rp, "second", "A", "a@b.com")
        history = get_commit_history(rp)
        result = get_diff_between(rp, history[1]["hash"], history[0]["hash"])
        assert "diff_text" in result
        assert "line2" in result["diff_text"]

    def test_diff_between_has_real_stats(self, articles_dir):
        """Bug 12: get_diff_between returns 'stats': {} — should compute real stats."""
        from peerpedia_core.storage.git_backend import (
            commit_article,
            get_commit_history,
            get_diff_between,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "test-diff-stats")
        (rp / "article.md").write_text("line1\n")
        commit_article_signed(rp, "first", "A", "a@b.com")
        (rp / "article.md").write_text("line1\nline2\n")
        commit_article_signed(rp, "second", "A", "a@b.com")
        history = get_commit_history(rp)
        result = get_diff_between(rp, history[1]["hash"], history[0]["hash"])
        # Stats should not be empty dict
        assert "stats" in result
        assert result["stats"] != {}
        # Should have at least some insertions or files
        insertions = result["stats"].get("total", {}).get("insertions", 0)
        assert insertions > 0


class TestBundleSync:
    """Git bundle create/apply — commit hash preservation across repos."""

    def test_ingest_and_merge_preserves_hash(self, articles_dir):
        """S1+S2: ingest + merge preserves commit hash when applied to empty repo."""
        import git as gitmod

        from peerpedia_core.bundle.git_bundle import ingest_bundle
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        # Client: create repo with two commits
        client_rp = init_article_repo(articles_dir / "client-article")
        (client_rp / "article.md").write_text("v1")
        h1 = commit_article_signed(client_rp, "first", "Author", "author@test.com")
        (client_rp / "article.md").write_text("v2")
        h2 = commit_article_signed(client_rp, "second", "Author", "author@test.com")
        assert h1 != h2

        # Create full bundle of all client objects
        import tempfile

        client_repo = gitmod.Repo(client_rp)
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
            bundle_path = f.name
        try:
            client_repo.git.bundle("create", bundle_path, "HEAD")
            full_bytes = Path(bundle_path).read_bytes()
        finally:
            Path(bundle_path).unlink(missing_ok=True)

        # Server: empty repo — ingest objects then merge (initial sync).
        # Use bare git init so the server starts with no commits, simulating
        # a fresh server that receives the client's full bundle.
        import git as _git

        server_rp = articles_dir / "server-article"
        server_rp.mkdir(parents=True, exist_ok=True)
        _git.Repo.init(server_rp)
        (server_rp / "reviews").mkdir(exist_ok=True)
        ingest_bundle(server_rp, full_bytes)
        server_repo = gitmod.Repo(server_rp)
        server_repo.git.merge("FETCH_HEAD")
        new_head = server_repo.head.commit.hexsha
        assert new_head == h2  # hash preserved!

        # Verify content and history (client's init commit + 2 content commits)
        assert len(list(server_repo.iter_commits())) == 3
        assert (server_rp / "article.md").read_text() == "v2"

    def test_create_incremental_bundle(self, articles_dir):
        """create_bundle returns bytes for since..HEAD range."""
        from peerpedia_core.bundle.git_bundle import create_bundle
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "incr-test")
        (rp / "article.md").write_text("v1")
        h1 = commit_article_signed(rp, "first", "Author", "author@test.com")
        (rp / "article.md").write_text("v2")
        commit_article_signed(rp, "second", "Author", "author@test.com")

        bundle = create_bundle(rp, h1)  # since first commit
        assert isinstance(bundle, bytes)
        assert len(bundle) > 0
        # Should be smaller than full repo (only contains objects after h1)
        assert len(bundle) < 10000

    def test_create_bundle_bad_since_raises(self, articles_dir):
        """create_bundle with non-ancestor since_hash raises ValueError."""
        from peerpedia_core.bundle.git_bundle import create_bundle
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "bad-since")
        (rp / "article.md").write_text("v1")
        commit_article_signed(rp, "first", "Author", "author@test.com")

        with pytest.raises(ValueError, match="not an ancestor"):
            create_bundle(rp, "0" * 40)  # nonexistent hash

    def test_create_bundle_bad_repo_raises(self, articles_dir):
        """create_bundle on non-existent repo raises FileNotFoundError."""
        from peerpedia_core.bundle.git_bundle import create_bundle

        with pytest.raises(FileNotFoundError):
            create_bundle(articles_dir / "nonexistent", "0" * 40)

    def test_ingest_bundle_bad_repo_raises(self, articles_dir):
        """ingest_bundle on non-existent repo raises FileNotFoundError."""
        from peerpedia_core.bundle.git_bundle import ingest_bundle

        with pytest.raises(FileNotFoundError):
            ingest_bundle(articles_dir / "nonexistent", b"garbage")

    def test_ingest_bundle_corrupt_raises(self, repo):
        """ingest_bundle with corrupt bytes raises ValueError."""
        from peerpedia_core.bundle.git_bundle import ingest_bundle

        with pytest.raises(ValueError, match="Invalid bundle"):
            ingest_bundle(repo, b"not a git bundle")

    def test_ingest_bundle_cleans_up_temp_file_on_verify_failure(self, repo, tmp_path, monkeypatch):
        """ingest_bundle removes the temp .bundle file even when verify fails."""
        import tempfile
        from peerpedia_core.bundle.git_bundle import ingest_bundle

        # Direct all temp files into a controlled directory.
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        with pytest.raises(ValueError, match="Invalid bundle"):
            ingest_bundle(repo, b"not a git bundle")

        # After the call, no .bundle files should remain.
        leftover = list(tmp_path.glob("*.bundle"))
        assert len(leftover) == 0, (
            f"Temp file leaked: {[str(p) for p in leftover]}"
        )

    def test_ff_only_merge_divergent_history(self, articles_dir):
        """ff-only merge on divergent history raises GitCommandError."""
        import git as gitmod

        from peerpedia_core.bundle.git_bundle import ingest_bundle
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        # Server has commit A → B
        server_rp = init_article_repo(articles_dir / "server-div")
        (server_rp / "article.md").write_text("sv1")
        commit_article_signed(server_rp, "sv1", "Svr", "svr@test.com")
        (server_rp / "article.md").write_text("sv2")
        commit_article_signed(server_rp, "sv2", "Svr", "svr@test.com")

        # Client has commit A → C (different second commit)
        client_rp = init_article_repo(articles_dir / "client-div")
        (client_rp / "article.md").write_text("cl1")
        commit_article_signed(client_rp, "cl1", "Cli", "cli@test.com")
        (client_rp / "article.md").write_text("cl2")
        commit_article_signed(client_rp, "cl2", "Cli", "cli@test.com")

        # Bundle from client (divergent from server)
        client_repo = gitmod.Repo(client_rp)
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
            bundle_path = f.name
        try:
            client_repo.git.bundle("create", bundle_path, "--all")
            bundle_bytes = Path(bundle_path).read_bytes()
        finally:
            Path(bundle_path).unlink(missing_ok=True)

        # Ingest succeeds (pure git — just adds objects)
        ingest_bundle(server_rp, bundle_bytes)
        # ff-only merge rejects divergent history (no MERGE_HEAD created)
        with pytest.raises(gitmod.GitCommandError):
            gitmod.Repo(server_rp).git.merge("FETCH_HEAD", "--ff-only")

    def test_lock_reuse(self):
        """get_article_lock returns same lock for same article_id."""
        from peerpedia_core.storage.locks import get_article_lock

        lock1 = get_article_lock("test-article")
        lock2 = get_article_lock("test-article")
        assert lock1 is lock2

    def test_lock_different_articles(self):
        """get_article_lock returns different locks for different article_ids."""
        from peerpedia_core.storage.locks import get_article_lock

        lock_a = get_article_lock("article-a")
        lock_b = get_article_lock("article-b")
        assert lock_a is not lock_b


# ═══════════════════════════════════════════════════════════════════════════════
# find_common_ancestor — interactive k-exponential + binary refinement
# ═══════════════════════════════════════════════════════════════════════════════


class TestFindCommonAncestor:
    """Interactive common ancestor search with mock probe."""

    def _make_repo_with_n_commits(
        self, base_dir: Path, article_id: str, n: int,
    ) -> tuple[Path, list[str]]:
        """Create a repo with *n* content commits (+ 1 init commit from init_article_repo).

        Returns (repo_path, hashes_from_HEAD) where:
          - hashes[0] = HEAD (most recent content commit)
          - hashes[n-1] = first content commit
          - hashes[n] = init commit
        """
        import git as _git

        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        rp = init_article_repo(base_dir / article_id)
        hashes = []
        for i in range(1, n + 1):
            (rp / "article.md").write_text(f"v{i}")
            h = commit_article_signed(rp, f"commit {i}", "Author", "a@b.com")
            hashes.append(h)
        hashes.reverse()  # index 0 = HEAD, index n-1 = first content commit
        hashes.append(list(_git.Repo(rp).iter_commits())[-1].hexsha)  # init commit
        return rp, hashes

    # ── Happy path tests ──────────────────────────────────────────────────

    def test_fork_at_probe_point(self, articles_dir):
        """Fork exactly at a probe distance (dist=5)."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "fork-probe", 10)

        # Fork at dist=5: dist 0-4 = False, dist >= 5 = True
        def probe(h: str) -> bool | None:
            idx = hashes.index(h)
            return idx >= 5

        result = find_common_ancestor(rp, probe)
        assert result == hashes[5]  # exact match at fork point

    def test_fork_between_probe_points(self, articles_dir):
        """Fork between probe points — binary refinement finds exact match."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "fork-between", 10)

        # Fork at dist=3: 0=False, 1=False, 5=True → binary in (1,5]
        def probe(h: str) -> bool | None:
            idx = hashes.index(h)
            return idx >= 3

        result = find_common_ancestor(rp, probe)
        assert result == hashes[3]  # binary refinement found exact fork

    def test_head_is_common_ancestor(self, articles_dir):
        """HEAD is common — remote is ahead or identical."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "head-common", 5)

        def probe(h: str) -> bool | None:
            return True  # all hashes exist on remote

        result = find_common_ancestor(rp, probe)
        assert result == hashes[0]  # HEAD

    def test_no_common_ancestor(self, articles_dir):
        """No common ancestor — all probes return False."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "no-common", 5)

        def probe(h: str) -> bool | None:
            return False  # none exist on remote

        result = find_common_ancestor(rp, probe)
        assert result is None

    # ── Error path tests ──────────────────────────────────────────────────

    def test_probe_returns_none_after_retries(self, articles_dir):
        """Probe returns None (network error) — retries exhausted → None."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "probe-none", 5)

        def probe(h: str) -> bool | None:
            return None  # network failure

        result = find_common_ancestor(rp, probe)
        assert result is None

    def test_empty_repo_raises(self, articles_dir):
        """Empty repo raises ValueError."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp = articles_dir / "empty-fca"
        rp.mkdir(parents=True, exist_ok=True)
        import git as _git

        _git.Repo.init(rp)
        with pytest.raises(ValueError, match="no commits"):
            find_common_ancestor(rp, lambda h: True)

    # ── Boundary tests ────────────────────────────────────────────────────

    def test_shallow_history(self, articles_dir):
        """Two commits, fork at dist=1 (binary refinement with tiny range)."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "shallow", 2)

        # Fork at dist=1: probe(HEAD)=False, probe(HEAD~1)=True
        def probe(h: str) -> bool | None:
            return h == hashes[1]

        result = find_common_ancestor(rp, probe)
        assert result == hashes[1]

    def test_deep_fork_within_max_depth(self, articles_dir):
        """Deep fork still within max_depth — found correctly."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        n = 200  # enough commits to exercise multiple probe rounds
        rp, hashes = self._make_repo_with_n_commits(articles_dir, "deep-fork", n)

        # Fork at dist=150
        def probe(h: str) -> bool | None:
            idx = hashes.index(h)
            return idx >= 150

        result = find_common_ancestor(rp, probe)
        assert result == hashes[150]

    def test_exhausts_max_depth(self, articles_dir):
        """Phase 1 exhausts all commits with no True → None."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "exhaust", 3)

        def probe(h: str) -> bool | None:
            return False  # never True

        result = find_common_ancestor(rp, probe, max_depth=3)
        assert result is None

    # ── Fast-path tests ────────────────────────────────────────────────────

    def test_server_head_is_common_ancestor(self, articles_dir):
        """Local ahead — server_head is in local history: 0 HTTP probes."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "local-ahead", 10)
        server_head = hashes[5]  # server is 5 commits behind local HEAD

        probe_calls = [0]

        def probe(h: str) -> bool | None:
            probe_calls[0] += 1
            # If server_head is truly the common ancestor, the server has
            # server_head and all older commits.  But the fast-path should
            # return before probe is ever called.
            return False  # should never be reached

        result = find_common_ancestor(rp, probe, server_head=server_head)
        assert result == server_head
        assert probe_calls[0] == 0  # zero HTTP calls

    def test_server_head_not_in_repo_falls_through(self, articles_dir):
        """server_head not in local repo (server ahead) — falls through to probe."""
        from peerpedia_core.bundle.git_bundle import find_common_ancestor

        rp, hashes = self._make_repo_with_n_commits(articles_dir, "svr-ahead-sp", 10)

        # server_head not in local repo → fast-path skipped → full search
        # probe returns True for HEAD → HEAD is common (server ahead)
        fake_server_head = "f" * 40
        result = find_common_ancestor(rp, lambda h: True, server_head=fake_server_head)
        assert result == hashes[0]  # HEAD returned by Phase 0 of full search

    def test_server_head_in_repo_but_not_ancestor(self, articles_dir):
        """server_head exists in repo but not on HEAD's chain — falls through."""
        import git

        from peerpedia_core.bundle.git_bundle import find_common_ancestor
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        rp = init_article_repo(articles_dir / "side-branch")
        repo = git.Repo(rp)

        # Create c1 as the initial commit
        (rp / "article.md").write_text("v1")
        c1 = commit_article_signed(rp, "c1", "Author", "a@b.com")

        # Create a side commit that is NOT on HEAD's chain:
        # save HEAD, create c2, then reset back
        main_ref = repo.head.commit.hexsha
        (rp / "article.md").write_text("v2-side")
        repo.git.add(A=True)
        c2 = repo.index.commit(
            "c2", author=git.Actor("Author", "a@b.com"),
            committer=git.Actor("Author", "a@b.com"),
        ).hexsha
        # Reset HEAD back to c1 — c2 is now orphaned (not on HEAD's chain)
        repo.head.reset(main_ref, index=True, working_tree=True)

        # c2 exists in repo but is_ancestor returns False (not on HEAD's chain).
        # Fast-path skips → full search finds c1.
        result = find_common_ancestor(
            rp, lambda h: h in (c1,), server_head=c2,
        )
        assert result == c1  # found by full search, not fast-path


# ═══════════════════════════════════════════════════════════════════════════════
# Closed-Loop Tests — full client ↔ server sync lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestClosedLoopSync:
    """Simulate a complete client-server sync cycle using only git operations.

    These tests verify the XSPEC specifications S1-S4 end-to-end:
    - S1: First push preserves commit hash
    - S2: Incremental push works after first sync
    - S3: Bidirectional pull-before-push
    - S4: Divergent history → 409 conflict
    """

    def _make_client_repo(
        self, base_dir: Path, article_id: str, content: str, author_name: str, author_email: str
    ) -> tuple[Path, str]:
        """Create a repo simulating a Tauri client with one commit. Returns (rp, head)."""
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        rp = init_article_repo(base_dir / article_id)
        (rp / "article.md").write_text(content)
        h = commit_article_signed(rp, "initial", author_name, author_email)
        return rp, h

    def test_full_lifecycle_s1_s2_s3(self, articles_dir):
        """S1+S2+S3: Create → push → verify hash → server change → pull → push again."""
        import git as gitmod

        from peerpedia_core.bundle.git_bundle import create_bundle, ingest_bundle
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        base = articles_dir

        # ── S1: Client creates article, pushes to server ──────────────────
        client_rp, h1 = self._make_client_repo(base, "lifecycle-s1", "# v1", "Alice", "alice@peerpedia.com")
        # Add second commit
        (client_rp / "article.md").write_text("# v2")
        h2 = commit_article_signed(client_rp, "second", "Alice", "alice@peerpedia.com")
        assert h1 != h2

        # Server starts with empty repo (bare init, no commits).
        # Simulates a fresh server receiving the client's first full upload.
        server_rp = base / "lifecycle-s1-server"
        server_rp.mkdir(parents=True, exist_ok=True)
        gitmod.Repo.init(server_rp)
        (server_rp / "reviews").mkdir(exist_ok=True)
        assert not gitmod.Repo(server_rp).head.is_valid()

        # Create full bundle of all client commits
        client_repo = gitmod.Repo(client_rp)
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
            client_repo.git.bundle("create", f.name, "HEAD")
            full_bundle = Path(f.name).read_bytes()
        Path(f.name).unlink(missing_ok=True)

        # Server: ingest + merge (initial sync)
        ingest_bundle(server_rp, full_bundle)
        gitmod.Repo(server_rp).git.merge("FETCH_HEAD")
        server_head = gitmod.Repo(server_rp).head.commit.hexsha
        assert server_head == h2  # S1: hash preserved!
        assert (server_rp / "article.md").read_text() == "# v2"

        # ── S3: Server adds a review commit; client pulls it ──────────────
        # Use gitignore-compliant path: reviews/*/scores.json
        review_dir = server_rp / "reviews" / "r1"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "scores.json").write_text('{"score": 5}')
        server_h_review = commit_article_signed(server_rp, "review commit", "Reviewer", "reviewer@peerpedia.com")
        assert server_h_review != h2

        # Client pulls server commits via incremental bundle
        incr_bundle = create_bundle(server_rp, h2)
        assert len(incr_bundle) > 0

        # Client: ingest + merge server's bundle
        ingest_bundle(client_rp, incr_bundle)
        gitmod.Repo(client_rp).git.merge("FETCH_HEAD")
        client_new_head = gitmod.Repo(client_rp).head.commit.hexsha
        assert client_new_head == server_h_review

        # Client now has the review commit
        client_repo2 = gitmod.Repo(client_rp)
        commits_after_pull = list(client_repo2.iter_commits())
        assert len(commits_after_pull) == 4  # init + v1 + v2 + review

        # ── S2: Client edits and pushes incrementally ─────────────────────
        (client_rp / "article.md").write_text("# v3 after review")
        client_h3 = commit_article_signed(client_rp, "v3 edit", "Alice", "alice@peerpedia.com")

        # Incremental bundle: server's HEAD → client's HEAD
        incr_bundle2 = create_bundle(client_rp, server_h_review)
        assert len(incr_bundle2) > 0

        # Server: ingest + merge incremental bundle
        ingest_bundle(server_rp, incr_bundle2)
        gitmod.Repo(server_rp).git.merge("FETCH_HEAD")
        server_head2 = gitmod.Repo(server_rp).head.commit.hexsha
        assert server_head2 == client_h3  # S2: incremental hash preserved!
        assert (server_rp / "article.md").read_text() == "# v3 after review"

        # Full cycle complete: client and server repos have identical history
        client_hashes = {c.hexsha for c in client_repo2.iter_commits()}
        server_commits = gitmod.Repo(server_rp)
        server_hashes = {c.hexsha for c in server_commits.iter_commits()}
        assert client_hashes == server_hashes

    def test_divergent_history_s4(self, articles_dir):
        """S4: Divergent commits on both sides → ff-only merge rejected."""
        import git as gitmod

        from peerpedia_core.bundle.git_bundle import create_bundle, ingest_bundle
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        base = articles_dir

        # Common ancestor
        client_rp, h1 = self._make_client_repo(base, "div-s4-client", "# shared v1", "Alice", "alice@test.com")
        (client_rp / "article.md").write_text("# shared v2")
        h2 = commit_article_signed(client_rp, "shared commit", "Alice", "alice@test.com")

        # Server starts from same ancestor (bare init — receives client's bundle)
        server_rp = base / "div-s4-server"
        server_rp.mkdir(parents=True, exist_ok=True)
        gitmod.Repo.init(server_rp)
        (server_rp / "reviews").mkdir(exist_ok=True)
        server_repo = gitmod.Repo(server_rp)
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
            gitmod.Repo(client_rp).git.bundle("create", f.name, "HEAD")
            full = Path(f.name).read_bytes()
        Path(f.name).unlink(missing_ok=True)
        ingest_bundle(server_rp, full)
        server_repo.git.merge("FETCH_HEAD")
        assert server_repo.head.commit.hexsha == h2

        # Client makes commit C
        (client_rp / "article.md").write_text("# client change")
        h_client = commit_article_signed(client_rp, "client edit", "Alice", "alice@test.com")

        # Server makes commit R (divergent)
        (server_rp / "article.md").write_text("# server change")
        h_server = commit_article_signed(server_rp, "server edit", "Bob", "bob@test.com")
        assert h_client != h_server

        # Client tries to push → ff-only merge rejects divergent history
        client_bundle = create_bundle(client_rp, h2)
        assert len(client_bundle) > 0

        ingest_bundle(server_rp, client_bundle)
        with pytest.raises(gitmod.GitCommandError):
            server_repo.git.merge("FETCH_HEAD", "--ff-only")


class TestCommitStatusMarker:
    """Tests for ``commit_status_marker`` — platform [status] commits."""

    def test_writes_platform_commit(self, articles_dir):
        from peerpedia_core.storage.git_backend import (
            commit_status_marker, init_article_repo, get_commit_history,
        )

        rp = init_article_repo(articles_dir / "test-status")
        (rp / "article.md").write_text("content")
        commit_article_signed(rp, "initial", "Author", "a@b.com")
        h = commit_status_marker(rp, "sedimentation")

        assert len(h) == 40
        commits = list(get_commit_history(rp, max_count=1))
        top = commits[0]
        assert top["hash"] == h
        assert "[status] sedimentation" in top["message"]
        assert top["author_email"] == "system@peerpedia"
        assert "PeerPedia" in top["author"]

    def test_rejects_invalid_status(self, articles_dir):
        from peerpedia_core.storage.git_backend import (
            commit_status_marker, init_article_repo,
        )

        rp = init_article_repo(articles_dir / "test-status-bad")
        (rp / "article.md").write_text("content")
        commit_article_signed(rp, "initial", "Author", "a@b.com")

        with pytest.raises(ValueError, match="Invalid status"):
            commit_status_marker(rp, "garbaggio")


# ── Branch Protection ───────────────────────────────────────────────────────


class TestBranchProtection:
    """Branch protection: all operations assert HEAD is on refs/heads/main."""

    def test_init_creates_on_main(self, articles_dir):
        """init_article_repo creates initial commit on main, not init.defaultBranch."""
        import git as _git
        from peerpedia_core.storage.git_backend import init_article_repo

        rp = init_article_repo(articles_dir / "test-init-main")
        repo = _git.Repo(rp)
        assert not repo.head.is_detached
        assert repo.head.reference.path == "refs/heads/main"

    def test_empty_repo_guard_noop(self, articles_dir):
        """_assert_on_main returns early (no-op) on empty repo with no commits."""
        import git as _git
        from peerpedia_core.storage.git_backend import _assert_on_main

        # Create empty repo with main branch but no commits
        rp = articles_dir / "test-empty"
        rp.mkdir()
        repo = _git.Repo.init(rp, initial_branch="main")
        # Should NOT raise — early return for empty repos
        _assert_on_main(repo)  # no exception

    def test_commit_on_wrong_branch_raises(self, articles_dir):
        """commit_article raises when HEAD is not on main."""
        import git as _git
        from peerpedia_core.storage.git_backend import init_article_repo

        rp = init_article_repo(articles_dir / "test-wrong-commit")
        repo = _git.Repo(rp)
        new_branch = repo.create_head("trunk")
        new_branch.checkout()
        (rp / "article.md").write_text("# Content\n")
        repo.git.add(A=True)

        # commit_article_signed calls commit_article internally; the guard
        # fires before signing, so the key derivation is irrelevant.
        with pytest.raises(RuntimeError, match="refs/heads/trunk"):
            commit_article_signed(rp, "commit on wrong branch", "Author", "a@b.com")

    def test_get_head_hash_on_wrong_branch_raises(self, articles_dir):
        """get_head_hash raises when HEAD is not on main."""
        import git as _git
        from peerpedia_core.storage.git_backend import get_head_hash, init_article_repo

        rp = init_article_repo(articles_dir / "test-wrong-head")
        repo = _git.Repo(rp)
        new_branch = repo.create_head("trunk")
        new_branch.checkout()

        with pytest.raises(RuntimeError, match="refs/heads/trunk"):
            get_head_hash(rp)

    def test_get_commit_history_on_wrong_branch_raises(self, articles_dir):
        """get_commit_history raises when HEAD is not on main."""
        import git as _git
        from peerpedia_core.storage.git_backend import get_commit_history, init_article_repo

        rp = init_article_repo(articles_dir / "test-wrong-history")
        repo = _git.Repo(rp)
        new_branch = repo.create_head("trunk")
        new_branch.checkout()

        with pytest.raises(RuntimeError, match="refs/heads/trunk"):
            get_commit_history(rp, max_count=5)

    def test_get_commit_authors_on_wrong_branch_raises(self, articles_dir):
        """get_commit_authors raises when HEAD is not on main."""
        import git as _git
        from peerpedia_core.storage.git_backend import get_commit_authors, init_article_repo

        rp = init_article_repo(articles_dir / "test-wrong-authors")
        repo = _git.Repo(rp)
        new_branch = repo.create_head("trunk")
        new_branch.checkout()

        with pytest.raises(RuntimeError, match="refs/heads/trunk"):
            get_commit_authors(rp)

    def test_detached_head_raises(self, articles_dir):
        """_assert_on_main raises RuntimeError on detached HEAD."""
        import git as _git
        from peerpedia_core.storage.git_backend import _assert_on_main, init_article_repo

        rp = init_article_repo(articles_dir / "test-detached")
        (rp / "article.md").write_text("# Content\n")
        commit_article_signed(rp, "commit", "Author", "a@b.com")

        repo = _git.Repo(rp)
        # Detach HEAD to the initial commit
        repo.head.reference = repo.head.commit
        # Now HEAD is detached — commit is the hexsha

        with pytest.raises(RuntimeError, match="detached"):
            _assert_on_main(repo)

    def test_merge_git_repos_target_wrong_branch_raises(self, articles_dir):
        """merge_git_repos raises when target is not on main."""
        import git as _git
        from peerpedia_core.storage.git_backend import (
            commit_article, init_article_repo, merge_git_repos,
        )

        # Target repo on "trunk" branch
        target_rp = articles_dir / "test-merge-target"
        target_rp.mkdir(parents=True)
        target_repo = _git.Repo.init(target_rp, initial_branch="trunk")
        (target_rp / "reviews").mkdir(exist_ok=True)
        (target_rp / "article.md").write_text("# Target\n")
        target_repo.git.add(A=True)
        target_repo.git.commit(m="target commit")

        # Fork repo on main
        fork_rp = init_article_repo(articles_dir / "test-merge-fork")
        (fork_rp / "article.md").write_text("# Fork\n")
        commit_article_signed(fork_rp, "fork commit", "Author", "a@b.com")

        with pytest.raises(RuntimeError, match="refs/heads/trunk"):
            merge_git_repos(target_rp, fork_rp, "Author")


# ── File cleanup robustness ──────────────────────────────────────────────


def test_commit_article_try_covers_temp_file_creation():
    """Regression: try block must start before _write_ssh_pubkey, not after.

    Verifies that the ``try`` keyword appears before the first temp file
    creation so that any exception during file setup is covered by finally.
    """
    import inspect
    from peerpedia_core.storage import git_backend as gb

    source = inspect.getsource(gb.commit_article)
    # After "if signing_key:", the next non-comment line must be the try.
    lines = [l.strip() for l in source.split("\n") if l.strip() and not l.strip().startswith("#")]
    found_signing = False
    for i, line in enumerate(lines):
        if "if signing_key:" in line:
            found_signing = True
            continue
        if found_signing:
            # Next substantive line should be "try:" or "pub_path = ..."
            # If try comes first, pub_path assignment is inside it. Either order is fine
            # as long as try covers the file writes.
            remaining = "\n".join(lines[i:])
            assert "try:" in remaining[:200], (
                "try block must cover temp file creation, but 'try:' not found "
                "within 200 chars after 'if signing_key:'"
            )
            break
