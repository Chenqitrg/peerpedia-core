# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for the help command."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.help import _cmd_meta_help

_MOD = 'peerpedia_core.cli.cmds.help'


def test_meta_help_no_topic_shows_overview(capsys):
    with patch(f'{_MOD}._HELP_DIR', create=True) as mock_dir:
        meta = mock_dir / "_meta.txt"
        meta.is_file.return_value = True
        meta.read_text.return_value = 'Welcome to PeerPedia!'
        _cmd_meta_help(Namespace(topic=None))
    assert 'Welcome to PeerPedia!' in capsys.readouterr().out


def test_meta_help_no_topic_fallback(capsys):
    with patch(f'{_MOD}._HELP_DIR', create=True) as mock_dir:
        meta = mock_dir / "_meta.txt"
        meta.is_file.return_value = False
        _cmd_meta_help(Namespace(topic=None))
    assert 'Try: peerpedia --help' in capsys.readouterr().out


def test_meta_help_with_topic_calls_subprocess():
    """subprocess is imported lazily inside the function — patch the stdlib."""
    with patch('subprocess.run') as mock_run:
        _cmd_meta_help(Namespace(topic='article'))
    mock_run.assert_called_once_with(['peerpedia', 'article', '--help'])
