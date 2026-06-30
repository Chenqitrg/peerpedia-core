# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Server start command.

LOCKED.  uvicorn.run blocks forever, so these tests mock it.
They verify parameter mapping and discovery thread behavior.
"""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.server import _cmd_server_start

_MOD = 'peerpedia_core.cli.cmds.server'


def test_server_start_defaults():
    """``peerpedia server start`` binds 127.0.0.1:8080 by default."""
    with patch('uvicorn.run') as mock_run:
        with patch('peerpedia_core.server.app.create_app'):
            _cmd_server_start(Namespace(host='127.0.0.1', port=8080, public_url=None))
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs['host'] == '127.0.0.1'
    assert kwargs['port'] == 8080
    assert kwargs['workers'] == 1


def test_server_start_custom_host_port():
    """``--host 0.0.0.0 --port 9000`` overrides defaults."""
    with patch('uvicorn.run') as mock_run:
        with patch('peerpedia_core.server.app.create_app'):
            _cmd_server_start(Namespace(host='0.0.0.0', port=9000, public_url=None))
    kwargs = mock_run.call_args.kwargs
    assert kwargs['host'] == '0.0.0.0'
    assert kwargs['port'] == 9000


def test_server_start_with_public_url_spawns_discovery():
    """``--public-url https://peer.example.com`` spawns a discovery thread."""
    with patch('uvicorn.run'):
        with patch('peerpedia_core.server.app.create_app'):
            with patch(f'{_MOD}._start_discovery_thread') as mock_thread:
                _cmd_server_start(Namespace(
                    host='127.0.0.1', port=8080,
                    public_url='https://peer.example.com'))
    mock_thread.assert_called_once_with('https://peer.example.com')


def test_server_start_empty_public_url_no_discovery():
    """Empty --public-url should not spawn discovery."""
    with patch('uvicorn.run'):
        with patch('peerpedia_core.server.app.create_app'):
            with patch(f'{_MOD}._start_discovery_thread') as mock_thread:
                _cmd_server_start(Namespace(
                    host='127.0.0.1', port=8080, public_url=''))
    mock_thread.assert_not_called()


def test_server_start_no_public_url_no_discovery():
    """No --public-url means no discovery thread."""
    with patch('uvicorn.run'):
        with patch('peerpedia_core.server.app.create_app'):
            with patch(f'{_MOD}._start_discovery_thread') as mock_thread:
                _cmd_server_start(Namespace(
                    host='127.0.0.1', port=8080, public_url=None))
    mock_thread.assert_not_called()
