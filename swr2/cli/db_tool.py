'''Database maintenance commands.'''

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta

from .. import db
from .. import paths
from ..defs import DEMO_FIXTURE_PATH
from ..logging_config import configure_logging


logger = logging.getLogger(__name__)


def seed_demo_tasks(clear: bool = False) -> int:
    '''Insert demo tasks from the fixture file and return the number added.'''
    if clear:
        db.delete_all_tasks()
    items = json.loads(DEMO_FIXTURE_PATH.read_text(encoding='utf-8'))
    now = datetime.now().replace(microsecond=0)
    for index, item in enumerate(items):
        timestamp = now - timedelta(days=item['days_ago'], minutes=index * 11)
        db.add_task_record(
            item['task'],
            item['description'],
            int(timestamp.timestamp()),
        )
    return len(items)


def main(argv: list[str] | None = None) -> int:
    '''Run database maintenance commands.'''
    configure_logging()
    parser = argparse.ArgumentParser(
        prog='db_tool',
        description=(
            'Database maintenance for simpleWorkReporter. A subcommand is '
            'required; running without one prints this help and exits.'
        ),
    )
    subparsers = parser.add_subparsers(dest='command', metavar='COMMAND')
    subparsers.add_parser(
        'init',
        help='create the tasks database if missing, then validate its schema',
        description=(
            'Create the tasks database file at the configured path if it does '
            'not exist, then validate that the schema matches the current '
            'application version. Safe to run repeatedly.'
        ),
    )
    demo_parser = subparsers.add_parser(
        'demo',
        help='insert sample tasks from fixtures/demo_tasks.json',
        description=(
            'Seed the database with sample task records from the bundled '
            'demo fixture. Implies init.'
        ),
    )
    demo_parser.add_argument(
        '--clear',
        action='store_true',
        help='delete every existing task before inserting demo entries',
    )
    demo_parser.add_argument(
        '-y',
        '--yes',
        action='store_true',
        help='skip the interactive confirmation for --clear',
    )
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2
    if args.command == 'init':
        return init([])
    if args.command == 'demo':
        demo_args = []
        if args.clear:
            demo_args.append('--clear')
        if args.yes:
            demo_args.append('--yes')
        return demo(demo_args)
    return 2


def init(argv: list[str] | None = None) -> int:
    '''Initialize or validate the database.'''
    parser = argparse.ArgumentParser(prog='db_tool init')
    parser.parse_args(argv)
    try:
        database = db.initialize_database()
    except db.DatabaseError as exc:
        logger.error('database validation failed error=%s', exc)
        print(f'Database error: {exc}', file=sys.stderr)
        return 1
    logger.info('database init completed path=%s', database)
    if sys.stdout.isatty():
        print(f'Database ready at {database}')
    return 0


def demo(argv: list[str] | None = None) -> int:
    '''Seed varied demo work entries.'''
    parser = argparse.ArgumentParser(prog='db_tool demo')
    parser.add_argument(
        '--clear',
        action='store_true',
        help='delete existing tasks before inserting demo entries',
    )
    parser.add_argument(
        '-y',
        '--yes',
        action='store_true',
        help='confirm destructive demo --clear without prompting',
    )
    args = parser.parse_args(argv)
    if args.clear and not args.yes and not _confirm_clear():
        logger.info('demo clear cancelled by user')
        if sys.stdout.isatty():
            print('Demo clear cancelled.')
        return 1
    try:
        db.initialize_database()
    except db.DatabaseError as exc:
        logger.error('database validation failed error=%s', exc)
        print(f'Database error: {exc}', file=sys.stderr)
        return 1
    count = seed_demo_tasks(clear=args.clear)
    logger.info('demo data seeded count=%s clear=%s', count, args.clear)
    if sys.stdout.isatty():
        print(f'Inserted {count} demo tasks into {paths.database_path()}')
    return 0


def _confirm_clear() -> bool:
    '''Prompt for confirmation before deleting task records.'''
    print('WARNING: ./db_tool demo --clear deletes every existing task record.')
    print(f'Database: {paths.database_path()}')
    try:
        response = input('Type "yes" to delete existing tasks and seed demo data: ')
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return response.strip().lower() == 'yes'


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
