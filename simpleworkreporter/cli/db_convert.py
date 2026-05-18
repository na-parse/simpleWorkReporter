'''Legacy v1 → v2 tasks database conversion.

The v1 schema stored task identity as two columns (`taskType`, `taskSubType`)
in a `swr_tasks` table; v2 collapses them into a single `task` column in a
`tasks` table living under SWR_HOME. This module copies rows across, joining
the two old columns with a space.

Invoked via `./swr db convert-swr1-db <path>`. This is a one-shot utility
kept as its own module so it can be removed once the v1 fleet is gone.
'''

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from .. import db
from .. import paths


# =============================================================================
# Conversion
# =============================================================================

def convert(source: Path, force: bool) -> int:
    '''Copy rows from a v1 tasks.db into the configured v2 database.'''
    if not source.exists():
        print(f'Source database not found: {source}', file=sys.stderr)
        return 1

    dest_path = paths.database_path()
    print(f'Source : {source}')
    print(f'Dest   : {dest_path}')

    try:
        db.initialize_database()
    except db.DatabaseError as exc:
        print(f'Destination database is unusable: {exc}', file=sys.stderr)
        return 1

    with sqlite3.connect(dest_path) as dest_conn:
        existing = dest_conn.execute(
            'SELECT COUNT(*) FROM tasks'
        ).fetchone()[0]
        if existing and not force:
            print(
                f'Destination already contains {existing} task(s); '
                'pass --force to append.',
                file=sys.stderr,
            )
            return 1

        rows = _read_legacy_rows(source)
        if not rows:
            print('Source database has no rows to convert.')
            return 0

        dest_conn.executemany(
            'INSERT INTO tasks (task, description, timestamp, sent) '
            'VALUES (?, ?, ?, ?)',
            rows,
        )
        dest_conn.commit()

    print(f'Converted {len(rows)} task(s).')
    return 0


def _read_legacy_rows(source: Path) -> list[tuple[str, str, int, int | None]]:
    '''Read v1 rows and project them onto the v2 column shape.'''
    with sqlite3.connect(source) as src_conn:
        src_conn.row_factory = sqlite3.Row
        cursor = src_conn.execute(
            'SELECT taskType, taskSubType, description, timestamp, sent '
            'FROM swr_tasks ORDER BY id'
        )
        return [_project_row(row) for row in cursor]


def _project_row(row: sqlite3.Row) -> tuple[str, str, int, int | None]:
    '''Map a v1 row tuple into v2 column values.'''
    task_type = (row['taskType'] or '').strip()
    task_subtype = (row['taskSubType'] or '').strip()
    task = f'{task_type} {task_subtype}'.strip()
    description = row['description'] or ''
    timestamp = int(row['timestamp'])
    sent_raw = row['sent']
    sent = int(sent_raw) if sent_raw else None
    return (task, description, timestamp, sent)


# =============================================================================
# Entry Point
# =============================================================================

def main(argv: list[str] | None = None) -> int:
    '''CLI entry point for `./swr db convert-swr1-db`.'''
    parser = argparse.ArgumentParser(
        prog='swr db convert-swr1-db',
        description='Convert a v1 simpleWorkReporter tasks.db to the v2 layout.',
    )
    parser.add_argument(
        'source',
        type=Path,
        help='path to the legacy v1 tasks.db file',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='append rows even if the destination already contains tasks',
    )
    args = parser.parse_args(argv)
    return convert(args.source, args.force)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
