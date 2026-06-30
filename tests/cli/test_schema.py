# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for the schema command."""

from __future__ import annotations

import json
from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.schema import _cmd_schema

_MOD = 'peerpedia_core.cli.cmds.schema'


def test_schema_prints_all_commands(capsys):
    with patch(f'{_MOD}._build_schema', return_value='{"version":"1.0","commands":[]}'):
        _cmd_schema(Namespace(command=None))
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data['version'] == '1.0'
    assert 'commands' in data


def test_schema_passes_target():
    with patch(f'{_MOD}._build_schema') as mock:
        _cmd_schema(Namespace(command='article'))
    mock.assert_called_once_with(target='article')


def test_schema_no_target():
    with patch(f'{_MOD}._build_schema') as mock:
        _cmd_schema(Namespace())
    mock.assert_called_once_with(target=None)
