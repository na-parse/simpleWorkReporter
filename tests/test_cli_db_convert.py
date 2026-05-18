'''Tests for `swr db convert-swr1-db` (v1 → v2 conversion).'''

from __future__ import annotations

import io
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from simpleworkreporter import db, paths
from simpleworkreporter.cli import db_convert, db_tool

from tests.support import TempHomeTestCase


# =============================================================================
# Helpers
# =============================================================================

def _build_v1_db(path: Path, rows: list[tuple[str, str, str, int, int | None]]) -> None:
    '''Create a legacy v1-shaped sqlite file at `path` and seed `rows`.

    Each row: (taskType, taskSubType, description, timestamp, sent).
    '''
    with sqlite3.connect(path) as conn:
        conn.execute(
            'CREATE TABLE swr_tasks ('
            '  id INTEGER PRIMARY KEY AUTOINCREMENT,'
            '  taskType TEXT,'
            '  taskSubType TEXT,'
            '  description TEXT,'
            '  timestamp INTEGER,'
            '  sent INTEGER'
            ')'
        )
        conn.executemany(
            'INSERT INTO swr_tasks (taskType, taskSubType, description, '
            'timestamp, sent) VALUES (?, ?, ?, ?, ?)',
            rows,
        )
        conn.commit()


# =============================================================================
# Tests
# =============================================================================

class DbConvertTests(TempHomeTestCase):
    def test_convert_into_empty_db_copies_and_joins_columns(self) -> None:
        source = Path(self.home_dir) / 'legacy.db'
        _build_v1_db(source, [
            ('Coding', 'Backend', 'wired up auth', 100, None),
            ('  ', '  ', 'whitespace-only types', 200, 1),
            ('Meeting', '', 'standup notes', 300, None),
        ])

        with patch('sys.stdout', new_callable=io.StringIO):
            rc = db_convert.main([str(source)])
        self.assertEqual(0, rc)

        with sqlite3.connect(paths.database_path()) as conn:
            rows = conn.execute(
                'SELECT task, description, timestamp, sent FROM tasks ORDER BY id'
            ).fetchall()
        self.assertEqual(
            [
                ('Coding Backend', 'wired up auth', 100, None),
                ('', 'whitespace-only types', 200, 1),
                ('Meeting', 'standup notes', 300, None),
            ],
            rows,
        )

    def test_convert_refuses_when_dest_has_rows_without_force(self) -> None:
        db.add_task_record('existing', 'pre-existing row', 1)
        source = Path(self.home_dir) / 'legacy.db'
        _build_v1_db(source, [('A', 'B', 'd', 1, None)])

        with (
            patch('sys.stdout', new_callable=io.StringIO),
            patch('sys.stderr', new_callable=io.StringIO),
        ):
            rc = db_convert.main([str(source)])
        self.assertEqual(1, rc)

    def test_convert_force_appends(self) -> None:
        db.add_task_record('existing', 'pre-existing row', 1)
        source = Path(self.home_dir) / 'legacy.db'
        _build_v1_db(source, [('A', 'B', 'new', 2, None)])

        with patch('sys.stdout', new_callable=io.StringIO):
            rc = db_convert.main([str(source), '--force'])
        self.assertEqual(0, rc)

        with sqlite3.connect(paths.database_path()) as conn:
            count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        self.assertEqual(2, count)

    def test_missing_source_errors(self) -> None:
        with patch('sys.stderr', new_callable=io.StringIO):
            rc = db_convert.main([str(Path(self.home_dir) / 'nope.db')])
        self.assertEqual(1, rc)

    def test_db_tool_dispatches_convert_subcommand(self) -> None:
        source = Path(self.home_dir) / 'legacy.db'
        _build_v1_db(source, [('A', 'B', 'd', 1, None)])

        with patch('sys.stdout', new_callable=io.StringIO):
            rc = db_tool.main(['convert-swr1-db', str(source)])
        self.assertEqual(0, rc)


if __name__ == '__main__':
    unittest.main()
