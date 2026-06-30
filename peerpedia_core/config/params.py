# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""All tunable system parameters — single source of truth.

To adjust any parameter, edit the defaults here or load from external config.
All tunable functions are replaceable so the community can iterate on mechanisms.
"""

from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════════════════════
# Identity constants
# ═══════════════════════════════════════════════════════════════════════════════

EMAIL_SUFFIX = "@peerpedia"
PLATFORM_EMAIL = f"system{EMAIL_SUFFIX}"


def make_peerpedia_email(local_part: str) -> str:
    """Build a PeerPedia email address from a local part.

    >>> make_peerpedia_email("system")
    'system@peerpedia'
    >>> make_peerpedia_email("user-123")
    'user-123@peerpedia'
    """
    return f"{local_part}{EMAIL_SUFFIX}"


def extract_user_id_from_email(email: str) -> str:
    """Extract the user_id from a PeerPedia email address.

    Inverse of ``make_peerpedia_email``.

    >>> extract_user_id_from_email("user-123@peerpedia")
    'user-123'
    """
    return email.split("@")[0]


# ── Article format constants ─────────────────────────────────────────────────

FMT_MARKDOWN = "markdown"
FMT_TYPST = "typst"
FMT_HTML = "html"
FMT_PDF = "pdf"
FMT_SVG = "svg"
FMT_PNG = "png"

_ARTICLE_EXT_TO_FMT = {
    ".md": FMT_MARKDOWN, ".markdown": FMT_MARKDOWN,
    ".typ": FMT_TYPST, ".typst": FMT_TYPST,
}
_ARTICLE_FMT_TO_EXT = {FMT_MARKDOWN: ".md", FMT_TYPST: ".typ"}
ARTICLE_EXTENSIONS = (".md", ".typ")
PEERPEDIA_SERVER_ENV = "PEERPEDIA_SERVER"

# ── Compiler constants ──────────────────────────────────────────────────────

TYPST_BIN = "typst"
TYPST_VALID_FMTS = (FMT_PDF, FMT_SVG, FMT_PNG)
TYPST_TIMEOUT = 30
TYPST_COMPILE_CMD = "compile"
TYPST_FORMAT_FLAG = "--format"
TYPST_WARNING_PREFIX = "warning:"

MD_EXTENSIONS = ("fenced_code", "tables", "codehilite", "pymdownx.arithmatex")
MD_ARITHMATEX_KEY = "pymdownx.arithmatex"
MD_OUTPUT_DIR = "compiled"


def article_format_to_ext(fmt: str) -> str:
    """Return the file extension for an article format name.

    >>> article_format_to_ext("markdown")
    '.md'
    >>> article_format_to_ext("typst")
    '.typ'
    """
    return _ARTICLE_FMT_TO_EXT[fmt]


def article_ext_to_format(ext: str) -> str:
    """Return the format name for an article file extension.

    >>> article_ext_to_format(".md")
    'markdown'
    """
    return _ARTICLE_EXT_TO_FMT[ext]


def article_filename(ext: str) -> str:
    """Return the article source filename for an extension.

    >>> article_filename(".md")
    'article.md'
    """
    return f"article{ext}"


@dataclass
class SinkParams:
    """Sedimentation pool timing parameters."""

    new_article_default_days: int = 7
    edit_article_default_days: int = 3
    min_days: int = 2
    scan_interval_seconds: int = 3600  # REPL periodic auto-publish interval
    max_days: int = 180
    max_sedimentation_per_author: int = 5  # anti-spam: max concurrent articles in pool

    # ReviewMetaStorage gate
    min_approvals: int = 3                # minimum reviewers who must approve (score ≥ threshold)
    approval_score_threshold: float = 3.0 # avg score ≥ this → "approve"
    review_deficit_extend_days: int = 3   # extra days when not enough reviewers
    max_total_sink_days: int = 21         # hard cap on total accumulated sink days (initial 7 + extensions)


@dataclass
class ScoreParams:
    """Scoring weights and tunable functions."""

    max_score: float = 5.0
    self_review_weight: float = 0.15
    community_weight: float = 0.85
    sedimentation_scope_weight: float = 1.0
    published_scope_weight: float = 0.5

    def score_to_sink_multiplier(self, avg_score: float) -> float:
        """Convert average score (0..5) to a sink-time multiplier (0..1).

        5.0 → multiplier ~0 (shortest sink), 0.0 → multiplier ~1 (longest sink).
        Linear interpolation: multiplier = 1 - (avg_score / max_score)
        """
        return 1.0 - (avg_score / self.max_score)

    def no_review_penalty(self) -> float:
        """Penalty applied when an article receives zero reviews in the pool.

        Returns a positive value that reduces the article's effective score.
        Default: 0.5 (equivalent to losing half a point).
        """
        return 0.5


@dataclass
class ReputationParams:
    """Reputation mechanism parameters (forward-looking)."""

    article_to_author_weight: float = 0.3
    author_weight_in_review: float = 0.2

    # Articles with score < this threshold are folded (frozen):
    # no new reviews, edits, forks, or citations allowed.
    fold_score_threshold: float = 1.0


@dataclass
class CommentParams:
    """Comment and thread parameters."""

    min_length: int = 200
    max_length: int = 300


@dataclass
class DiscoveryParams:
    """P2P network discovery parameters."""

    seed_peers: tuple[str, ...] = (
        "https://seed1.peerpedia.org",
        "https://seed2.peerpedia.org",
    )
    max_known_peers: int = 50


@dataclass
class ServerParams:
    """Server and middleware parameters."""

    # Rate limiting
    rate_limit_requests_per_window: int = 60
    rate_limit_window_seconds: int = 10

    # Logging
    log_slow_request_ms: float = 500.0

    # Bundle size
    max_bundle_bytes: int = 100 * 1024 * 1024  # 100 MB

    # DB session — paths that don't need a DB connection (git-only)
    db_skip_prefixes: tuple[str, ...] = ("/health",)

    # Client
    stale_server_warn_after: int = 3  # consecutive offline checks before warning
    db_skip_suffixes: tuple[str, ...] = ("/head", "/bundle", "/repo")
    db_skip_contains: tuple[str, ...] = ("/ancestor/",)

    # Login rate limiting — account lockout after repeated failures
    max_failed_login_attempts: int = 5
    login_lockout_minutes: int = 15

    # Auth — paths that don't require authentication
    auth_public_prefixes: tuple[str, ...] = ("/health", "/api/v1/school")
    auth_public_suffixes: tuple[str, ...] = (
        "/head", "/bundle", "/sync", "/repo",
        "/following", "/followers", "/articles", "/shares",
    )
    auth_public_contains: tuple[str, ...] = ("/ancestor/",)


@dataclass
class Params:
    """Aggregate of all tunable parameter groups."""

    sink: SinkParams = field(default_factory=SinkParams)
    score: ScoreParams = field(default_factory=ScoreParams)
    reputation: ReputationParams = field(default_factory=ReputationParams)
    comment: CommentParams = field(default_factory=CommentParams)
    discovery: DiscoveryParams = field(default_factory=DiscoveryParams)
    server: ServerParams = field(default_factory=ServerParams)


params = Params()
