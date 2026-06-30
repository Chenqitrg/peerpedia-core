# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for article commands and helpers."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock, patch

from peerpedia_core.cli.cmds.article import (
    _get_article_content,
    _compute_edit_diff,
    _cmd_article_create,
    _cmd_article_show,
    _cmd_article_list,
    _cmd_article_edit,
    _cmd_article_publish,
    _cmd_article_delete,
    _cmd_article_scan,
    _cmd_article_diff,
    _cmd_compile,
)
from tests.cli.conftest import call, mock_cmd, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.article'


# ── _get_article_content ──────────────────────────────────────────────────

def test_get_content_from_arg():
    args = Namespace(content='Hello\\nWorld', no_editor=False)
    result = _get_article_content(args)
    assert result == 'Hello\nWorld'


def test_get_content_unscape_tabs():
    args = Namespace(content='col1\\tcol2', no_editor=False)
    result = _get_article_content(args)
    assert result == 'col1\tcol2'


def test_get_content_from_editor():
    args = Namespace(content=None, no_editor=False)
    with patch(f'{_MOD}.sys.stdout.isatty', return_value=True):
        with patch(f'{_MOD}._open_editor', return_value='Written in editor'):
            result = _get_article_content(args)
    assert result == 'Written in editor'


def test_get_content_no_editor():
    args = Namespace(content=None, no_editor=True)
    result = _get_article_content(args)
    assert result == ''


# ── _compute_edit_diff ────────────────────────────────────────────────────

def test_compute_diff_content_changed():
    result = _compute_edit_diff('old\nline', 'new\nline', None, True)
    assert '--- a/article.md' in result
    assert '+++ b/article.md' in result


def test_compute_diff_title_only():
    result = _compute_edit_diff('same', None, 'New Title', False)
    assert result == 'Title: New Title'


def test_compute_diff_no_changes():
    result = _compute_edit_diff('same', None, None, False)
    assert result == ''


# ── Create ────────────────────────────────────────────────────────────────

def test_article_create_delegates(ctx):
    with mock_cmd(_MOD, '_article') as app:
        args = Namespace(title='Paper', format='markdown', content='Body',
                         publish=False, scores=None)
        call(_cmd_article_create, ctx, args)
    app.create.assert_called_once_with(
        ctx, title='Paper', format='markdown', content='Body',
        publish=False, scores_str=None)


def test_article_create_publish_with_scores(ctx):
    with mock_cmd(_MOD, '_article') as app:
        args = Namespace(title='Paper', format='typst', content='Body',
                         publish=True, scores='orig=5')
        call(_cmd_article_create, ctx, args)
    app.create.assert_called_once_with(
        ctx, title='Paper', format='typst', content='Body',
        publish=True, scores_str='orig=5')


# ── Show ──────────────────────────────────────────────────────────────────

def test_article_show_json_returns_early(ctx):
    with mock_cmd(_MOD, '_article') as app:
        args = Namespace(id='abc', json=True, show='full')
        call(_cmd_article_show, ctx, args)
    app.show.assert_called_once_with(ctx, article_ref='abc')
    app.get_source_path.assert_not_called()


def test_article_show_meta_returns_early(ctx):
    with mock_cmd(_MOD, '_article') as app:
        args = Namespace(id='abc', json=False, show='meta')
        call(_cmd_article_show, ctx, args)
    app.show.assert_called_once_with(ctx, article_ref='abc')
    app.get_source_path.assert_not_called()


# ── List ──────────────────────────────────────────────────────────────────

def test_article_list_delegates_all_filters(ctx):
    with mock_cmd(_MOD, '_article') as app:
        args = Namespace(search='quantum', status='draft', mine=True,
                         feed=False, bookmarked=False, user=None, server=None)
        call(_cmd_article_list, ctx, args)
    app.list_articles.assert_called_once_with(
        ctx, search_query='quantum', status_arg='draft', mine=True,
        feed=False, bookmarked=False, user_ref=None, server=None, limit=20)


# ── Edit ──────────────────────────────────────────────────────────────────

def test_article_edit_content_changed(ctx):
    with mock_cmd(_MOD, '_article') as app:
        app.get_source_path.return_value = MagicMock(
            data={'content': 'old content'})
        with patch(f'{_MOD}._prompt_commit_message', return_value='Edited article'):
            call(_cmd_article_edit, ctx,
                 Namespace(id='abc', content='new content', title=None,
                           no_editor=False))
    app.edit.assert_called_once_with(
        ctx, article_ref='abc', content='new content', title=None,
        message='Edited article')


def test_article_edit_title_changed(ctx):
    """Title-only edit auto-generates commit message, no editor prompt."""
    with mock_cmd(_MOD, '_article') as app:
        app.get_source_path.return_value = MagicMock(
            data={'content': 'same content'})
        with patch(f'{_MOD}._open_editor', return_value='same content'):
            call(_cmd_article_edit, ctx,
                 Namespace(id='abc', content=None, title='New Title',
                           no_editor=False))
    app.edit.assert_called_once_with(
        ctx, article_ref='abc', content='same content', title='New Title',
        message='Title: New Title')


# ── Publish / Delete / Scan ───────────────────────────────────────────────

def test_article_publish_delegates(ctx):
    with mock_spec_handler(_MOD, 'article.publish') as h:
        call(_cmd_article_publish, ctx, Namespace(id='abc', scores='orig=5'))
    h.assert_called_once_with(ctx, {'id': 'abc', 'scores': 'orig=5'})


def test_article_delete_delegates(ctx):
    with mock_spec_handler(_MOD, 'article.delete') as h:
        call(_cmd_article_delete, ctx, Namespace(id='abc'))
    h.assert_called_once_with(ctx, {'id': 'abc'})


def test_article_scan_delegates(ctx):
    with mock_spec_handler(_MOD, 'article.scan') as h:
        call(_cmd_article_scan, ctx, Namespace())
    h.assert_called_once_with(ctx, {})


# ── Diff ──────────────────────────────────────────────────────────────────

def test_article_diff_delegates(ctx):
    with mock_spec_handler(_MOD, 'article.diff') as h:
        h.return_value = MagicMock(data={'diff_text': '-old\n+new', 'stats': {}})
        call(_cmd_article_diff, ctx, Namespace(id='abc', hash1='~1', hash2='HEAD'))
    h.assert_called_once_with(
        ctx, {'id': 'abc', 'hash1': '~1', 'hash2': 'HEAD'})


# ── Compile ───────────────────────────────────────────────────────────────

def test_compile_source_not_found(ctx):
    with mock_cmd(_MOD, '_article') as app:
        app.get_source_path.return_value = MagicMock(data={'path': ''})
        with patch(f'{_MOD}._out') as mock_out:
            call(_cmd_compile, ctx, Namespace(id='abc'))
    mock_out.assert_called_once()
    assert mock_out.call_args[0][1] == 'SOURCE_NOT_FOUND'


def test_compile_success(ctx):
    with mock_cmd(_MOD, '_article') as app:
        app.get_source_path.return_value = MagicMock(data={'path': '/tmp/a.md'})
        result = MagicMock()
        result.success = True
        result.output_path = '/tmp/a.pdf'
        result.html_content = ''
        with patch(f'{_MOD}.compile_article', return_value=result):
            with patch(f'{_MOD}._out'):
                call(_cmd_compile, ctx, Namespace(id='abc', format='pdf'))
    # No exception = success; _out is called for N_COMPILED
