# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/git/trailers.py — commit trailer parsing."""


# ═══════════════════════════════════════════════════════════════════════════════
# parse_closes_trailer
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseClosesTrailer:
    def test_extracts_reviewer_and_thread(self):
        """Parses 'Closes: review/reviewer-dir/thread-3' → (reviewer_dir, thread_num)."""
        from peerpedia_core.storage.git.trailers import parse_closes_trailer

        result = parse_closes_trailer("Closes: review/alice-review/thread-3")
        assert result == ("alice-review", 3)

    def test_case_insensitive(self):
        """Closes: trailer parsing is case-insensitive."""
        from peerpedia_core.storage.git.trailers import parse_closes_trailer

        result = parse_closes_trailer("closes: review/bob/thread-7")
        assert result == ("bob", 7)

    def test_multiline_message_parses(self):
        """Trailer is found within a full commit message body."""
        from peerpedia_core.storage.git.trailers import parse_closes_trailer

        message = "Edit section 3\n\nApplied reviewer feedback.\nCloses: review/carol-r/thread-12\n"
        result = parse_closes_trailer(message)
        assert result == ("carol-r", 12)

    def test_no_trailer_returns_none(self):
        """Commit message without Closes: returns None."""
        from peerpedia_core.storage.git.trailers import parse_closes_trailer

        assert parse_closes_trailer("Just a regular commit") is None

    def test_malformed_trailer_returns_none(self):
        """Malformed Closes: (no thread number) returns None."""
        from peerpedia_core.storage.git.trailers import parse_closes_trailer

        # Missing thread-{n} part
        assert parse_closes_trailer("Closes: review/alice") is None


# ═══════════════════════════════════════════════════════════════════════════════
# validate_closes_target
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateClosesTarget:
    def test_existing_file_returns_true(self, tmp_path, monkeypatch):
        """Thread file exists → returns True — Closes: reference is valid."""
        from peerpedia_core.storage.git.trailers import validate_closes_target

        thread_file = tmp_path / "article-id" / "reviews" / "alice" / "threads" / "003.md"
        thread_file.parent.mkdir(parents=True)
        thread_file.write_text("# Thread 3")
        monkeypatch.setattr(
            "peerpedia_core.storage.git.trailers.DEFAULT_ARTICLES_DIR", tmp_path,
        )
        assert validate_closes_target("article-id", "alice", 3) is True

    def test_missing_file_returns_false(self, tmp_path, monkeypatch):
        """Thread file doesn't exist → returns False — invalid reference."""
        from peerpedia_core.storage.git.trailers import validate_closes_target

        monkeypatch.setattr(
            "peerpedia_core.storage.git.trailers.DEFAULT_ARTICLES_DIR", tmp_path,
        )
        assert validate_closes_target("article-id", "alice", 3) is False


# ═══════════════════════════════════════════════════════════════════════════════
# list_review_threads
# ═══════════════════════════════════════════════════════════════════════════════


class TestListReviewThreads:
    def test_lists_threads(self, tmp_path, monkeypatch):
        """Enumerates review/{dir}/thread-{n} paths for a valid article."""
        from peerpedia_core.storage.git.trailers import list_review_threads

        # Create review threads
        thread1 = tmp_path / "art-1" / "reviews" / "alice" / "threads" / "001.md"
        thread1.parent.mkdir(parents=True)
        thread1.write_text("# Thread 1")

        thread2 = tmp_path / "art-1" / "reviews" / "alice" / "threads" / "002.md"
        thread2.write_text("# Thread 2")

        thread3 = tmp_path / "art-1" / "reviews" / "bob" / "threads" / "001.md"
        thread3.parent.mkdir(parents=True)
        thread3.write_text("# Thread 1")

        monkeypatch.setattr(
            "peerpedia_core.storage.git.trailers.DEFAULT_ARTICLES_DIR", tmp_path,
        )
        threads = list_review_threads("art-1")
        assert len(threads) == 3
        assert "review/alice/thread-001" in threads
        assert "review/alice/thread-002" in threads
        assert "review/bob/thread-001" in threads

    def test_no_reviews_dir_returns_empty(self, tmp_path, monkeypatch):
        """Article without reviews/ dir returns empty list."""
        from peerpedia_core.storage.git.trailers import list_review_threads

        monkeypatch.setattr(
            "peerpedia_core.storage.git.trailers.DEFAULT_ARTICLES_DIR", tmp_path,
        )
        assert list_review_threads("art-no-reviews") == []
