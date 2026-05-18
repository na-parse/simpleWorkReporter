'''Tests for the ./swr top-level dispatcher.'''

from __future__ import annotations

import importlib.util
import io
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch


# Load ./swr (no .py extension) as a module so we can call main() directly.
REPO_DIR = Path(__file__).resolve().parent.parent
_LOADER = SourceFileLoader('_swr_dispatcher', str(REPO_DIR / 'swr'))
_SPEC = importlib.util.spec_from_loader('_swr_dispatcher', _LOADER)
swr_dispatcher = importlib.util.module_from_spec(_SPEC)
_LOADER.exec_module(swr_dispatcher)


class DispatcherTests(unittest.TestCase):
    def test_no_argv_prints_help_to_stdout_and_returns_2(self) -> None:
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            rc = swr_dispatcher.main([])
        self.assertEqual(2, rc)
        self.assertIn('Usage: ./swr', out.getvalue())

    def test_help_flag_returns_0(self) -> None:
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            rc = swr_dispatcher.main(['--help'])
        self.assertEqual(0, rc)
        self.assertIn('Verbs', out.getvalue())

    def test_unknown_verb_writes_stderr_and_returns_2(self) -> None:
        with (
            patch('sys.stdout', new_callable=io.StringIO),
            patch('sys.stderr', new_callable=io.StringIO) as err,
        ):
            rc = swr_dispatcher.main(['nope'])
        self.assertEqual(2, rc)
        self.assertIn("unknown verb 'nope'", err.getvalue())

    def test_setup_alias_config_dispatches_to_same_handler(self) -> None:
        self.assertIs(
            swr_dispatcher.VERBS['setup'],
            swr_dispatcher.VERBS['config'],
        )

    def test_all_expected_verbs_present(self) -> None:
        self.assertEqual(
            {'start', 'setup', 'config', 'db', 'cert', 'send'},
            set(swr_dispatcher.VERBS),
        )

    def test_verb_forwards_argv_tail(self) -> None:
        # VERBS captures handler references at import time; patch the dict
        # entry directly so the dispatcher picks up the stub.
        from unittest.mock import MagicMock
        stub = MagicMock(return_value=0)
        with patch.dict(swr_dispatcher.VERBS, {'db': stub}):
            rc = swr_dispatcher.main(['db', 'init', '--extra'])
        self.assertEqual(0, rc)
        stub.assert_called_once_with(['init', '--extra'])


if __name__ == '__main__':
    unittest.main()
