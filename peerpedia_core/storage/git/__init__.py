# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git storage layer — core operations and guards."""

from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR  # noqa: F401
from peerpedia_core.exceptions import MergeConflictError  # noqa: F401 — re-exported

from peerpedia_core.storage.git.ops import (
    commit_article,
    commit_status_marker,
    delete_article_repo,
    init_article_repo,
    is_repo_dirty,
)

from peerpedia_core.storage.git.read import (
    assert_on_main,
    get_commit_authors,
    get_commit_history,
    get_diff_between,
    get_head_commit,
    get_head_hash,
    get_head_or_none,
    is_ancestor,
    list_review_dirs,
    read_article_source,
    read_review_scores,
    read_status_from_git,
    resolve_article_format,
)

from peerpedia_core.storage.git.ancestor import find_common_ancestor

from peerpedia_core.storage.git.merge import (
    checkout_files,
    clone_article_repo,
    merge_fetch_head,
    merge_git_repos,
    reset_to_commit,
    rollback_to,
)

from peerpedia_core.storage.git.bundle import (
    create_bundle,
    get_head,
    ingest_bundle,
)

from peerpedia_core.storage.git.archive import (
    ingest_article,
    ingest_article_repo,
    pack_article_repo,
)

from peerpedia_core.storage.git.trailers import (
    list_review_threads,
    parse_closes_trailer,
    validate_closes_target,
)

from peerpedia_core.storage.git.guards import (
    assert_repo_on_main,
    extract_pubkey_from_message,
    guard_not_empty,
    require_article_repo,
    require_commit_pubkey_signature,
    require_commit_signing_key,
    require_review_scores,
    require_signing_key_for_pubkey,
    require_valid_article_status,
    verify_commit_signature,
)
