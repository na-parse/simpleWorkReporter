'''SQLite task storage.'''

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from . import paths
from .defs import (
    DEFAULT_BACKDATED_TIME,
    SEND_LOCK_SEED_SQL,
    SEND_LOCK_STALE_SECONDS,
    SEND_LOCK_TABLE_SQL,
    TASK_TABLE_SQL,
)


logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    '''Raised when the configured task database is missing or corrupt.

    Validated once at startup; downstream code may assume the DB is usable
    for the lifetime of the process.
    '''


class SendLockBusy(Exception):
    '''Raised when send_lock acquisition fails because the lock is held.

    Carries no payload beyond a human-facing message; the lock model is
    fail-fast (no wait/retry) so the operator gets immediate feedback.
    '''


@dataclass(frozen=True)
class Task:
    id: int
    task: str
    description: str
    timestamp: int
    sent: int | None

    @property
    def display_date(self) -> str:
        '''Return the user-facing date for a task.'''
        return timestamp_to_date(self.timestamp)

    @property
    def sent_date(self) -> str:
        '''Return the user-facing sent date, if any.'''
        if self.sent is None:
            return ''
        return timestamp_to_date(self.sent)

    @property
    def is_sent(self) -> bool:
        '''Return whether this task has been included in a report.'''
        return self.sent is not None


class _Connection:
    '''Short-lived sqlite3 connection with deterministic close.

    sqlite3.Connection's own context manager commits/rolls back but does
    not close — leaking the fd until garbage collection. This wrapper
    opens on enter, commits or rolls back on exit, then closes.
    '''

    def __init__(self, path: Path | None = None):
        self._path = path or paths.database_path()
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self._conn is not None
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None


def initialize_database(path: Path | None = None) -> Path:
    '''Validate the task database, creating it if absent.

    Raises DatabaseError when the file exists but is not a valid sqlite
    database or is missing the tasks table.
    '''
    database = path or paths.database_path()
    if not database.exists():
        database.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(database)
        try:
            conn.execute(TASK_TABLE_SQL)
            conn.execute(SEND_LOCK_TABLE_SQL)
            conn.execute(SEND_LOCK_SEED_SQL)
            conn.commit()
        finally:
            conn.close()
        logger.info('task database created path=%s', database)
        return database
    try:
        conn = sqlite3.connect(database)
        try:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(
            f'File at {database} is not a valid sqlite database: {exc}'
        ) from exc
    missing = {'tasks', 'send_lock'} - tables
    if missing:
        raise DatabaseError(
            f'sqlite file at {database} is missing expected table(s) '
            f'{sorted(missing)}. Delete the file to re-initialize.'
        )
    logger.debug('task database validated path=%s', database)
    return database


def add_task(task: str, description: str, timestamp: int | None = None) -> int:
    '''Add a task and return its ID.'''
    stamp = timestamp if timestamp is not None else now_stamp()
    with _Connection() as conn:
        cursor = conn.execute(
            'INSERT INTO tasks (task, description, timestamp) VALUES (?, ?, ?)',
            (task.strip(), description.strip(), stamp),
        )
        task_id = cursor.lastrowid
    logger.info(
        'task inserted id=%s task=%r timestamp=%s description_chars=%s',
        task_id,
        task.strip(),
        stamp,
        len(description.strip()),
    )
    return task_id


def add_task_record(
    task: str,
    description: str,
    timestamp: int,
    sent: int | None = None,
) -> int:
    '''Add a task record with an explicit sent value.'''
    with _Connection() as conn:
        cursor = conn.execute(
            '''
            INSERT INTO tasks (task, description, timestamp, sent)
            VALUES (?, ?, ?, ?)
            ''',
            (task.strip(), description.strip(), timestamp, sent),
        )
        task_id = cursor.lastrowid
    logger.info(
        'task record inserted id=%s task=%r timestamp=%s sent=%s description_chars=%s',
        task_id,
        task.strip(),
        timestamp,
        sent,
        len(description.strip()),
    )
    return task_id


def delete_all_tasks() -> None:
    '''Delete all task records.'''
    with _Connection() as conn:
        cursor = conn.execute('DELETE FROM tasks')
    logger.info('all task records deleted count=%s', cursor.rowcount)


def update_task(task_id: int, task: str, description: str, timestamp: int) -> None:
    '''Update an existing task.'''
    with _Connection() as conn:
        cursor = conn.execute(
            '''
            UPDATE tasks
               SET task = ?, description = ?, timestamp = ?
             WHERE id = ?
            ''',
            (task.strip(), description.strip(), timestamp, task_id),
        )
    logger.info(
        'task updated id=%s rows=%s task=%r timestamp=%s description_chars=%s',
        task_id,
        cursor.rowcount,
        task.strip(),
        timestamp,
        len(description.strip()),
    )


def delete_task(task_id: int) -> None:
    '''Delete a task by ID.'''
    with _Connection() as conn:
        cursor = conn.execute(
            'DELETE FROM tasks WHERE id = ?', (task_id,)
        )
    logger.info('task deleted id=%s rows=%s', task_id, cursor.rowcount)


def get_task(task_id: int) -> Task | None:
    '''Return one task by ID.'''
    with _Connection() as conn:
        row = conn.execute(
            'SELECT * FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
    logger.debug('task loaded id=%s found=%s', task_id, row is not None)
    return _task_from_row(row) if row else None


def all_tasks() -> list[Task]:
    '''Return all tasks, newest first.'''
    with _Connection() as conn:
        rows = conn.execute(
            'SELECT * FROM tasks ORDER BY timestamp DESC, id DESC'
        ).fetchall()
    logger.debug('all tasks loaded count=%s', len(rows))
    return [_task_from_row(row) for row in rows]


def unsent_tasks() -> list[Task]:
    '''Return unsent tasks, oldest first for report readability.'''
    with _Connection() as conn:
        rows = conn.execute(
            '''
            SELECT * FROM tasks
             WHERE sent IS NULL
             ORDER BY timestamp ASC, id ASC
            '''
        ).fetchall()
    logger.debug('unsent tasks loaded count=%s', len(rows))
    return [_task_from_row(row) for row in rows]


def count_unsent() -> int:
    '''Return the number of unsent tasks.'''
    with _Connection() as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS task_count FROM tasks WHERE sent IS NULL'
        ).fetchone()
    count = int(row['task_count'])
    logger.debug('unsent task count loaded count=%s', count)
    return count


def mark_sent(task_ids: Iterable[int], sent_timestamp: int | None = None) -> None:
    '''Mark a provided set of task IDs as sent in one transaction.'''
    ids = list(task_ids)
    if not ids:
        return
    stamp = sent_timestamp if sent_timestamp is not None else now_stamp()
    placeholders = ','.join('?' for _ in ids)
    with _Connection() as conn:
        cursor = conn.execute(
            f'''
            UPDATE tasks
               SET sent = ?
             WHERE sent IS NULL
               AND id IN ({placeholders})
            ''',
            [stamp, *ids],
        )
    logger.info(
        'tasks marked sent requested_count=%s updated_count=%s sent_timestamp=%s',
        len(ids),
        cursor.rowcount,
        stamp,
    )


class send_lock:
    '''Atomic send mutex backed by the single-row send_lock table.

    Use as a context manager. The lock is acquired with a single UPDATE
    that succeeds only when the table row is free OR holds a stale claim
    (older than SEND_LOCK_STALE_SECONDS), so a crashed sender cannot lock
    the operation forever.

    `force=True` skips the freshness guard entirely — the caller takes
    over whatever claim exists. Reserved for the `send_report --force`
    operator escape hatch; logs loudly when it overrides a held claim.
    '''

    def __init__(self, force: bool = False):
        self._force = force

    def __enter__(self) -> 'send_lock':
        now = now_stamp()
        with _Connection() as conn:
            prior = conn.execute(
                'SELECT acquired_at FROM send_lock WHERE id = 1'
            ).fetchone()
            prior_value = prior['acquired_at'] if prior else None
            if self._force:
                conn.execute(
                    'UPDATE send_lock SET acquired_at = ? WHERE id = 1',
                    (now,),
                )
                if prior_value is not None:
                    logger.warning(
                        'send_lock force-acquired over existing claim '
                        'acquired_at=%s now=%s',
                        prior_value, now,
                    )
                else:
                    logger.info('send_lock force-acquired (lock was free)')
                return self
            stale_cutoff = now - SEND_LOCK_STALE_SECONDS
            cursor = conn.execute(
                '''
                UPDATE send_lock
                   SET acquired_at = ?
                 WHERE id = 1
                   AND (acquired_at IS NULL OR acquired_at < ?)
                ''',
                (now, stale_cutoff),
            )
        if cursor.rowcount != 1:
            raise SendLockBusy(
                'Another send appears to be in progress. Try again in a '
                'few minutes, or re-run with --force to override.'
            )
        if prior_value is not None:
            logger.info(
                'send_lock acquired over stale claim acquired_at=%s now=%s',
                prior_value, now,
            )
        else:
            logger.debug('send_lock acquired now=%s', now)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        with _Connection() as conn:
            conn.execute(
                'UPDATE send_lock SET acquired_at = NULL WHERE id = 1'
            )
        logger.debug('send_lock released')


def date_range(tasks: list[Task]) -> str:
    '''Compute a display date range for tasks.'''
    if not tasks:
        return ''
    dates = [task.display_date for task in tasks]
    start = min(dates)
    end = max(dates)
    if start == end:
        return start
    return f'{start} to {end}'


def now_stamp() -> int:
    '''Return the current Unix epoch in seconds (local-naive semantics).'''
    return int(time.time())


def date_to_timestamp(date_value: str) -> int:
    '''Convert an HTML date value into an epoch timestamp.

    Today (or empty) returns the current full timestamp so same-day entries
    keep their creation order. Back-dated entries collapse to
    DEFAULT_BACKDATED_TIME on that date.
    '''
    today_iso = datetime.now().date().isoformat()
    if not date_value or date_value == today_iso:
        return now_stamp()
    parsed = datetime.strptime(date_value, '%Y-%m-%d')
    hour, minute, second = DEFAULT_BACKDATED_TIME
    parsed = parsed.replace(hour=hour, minute=minute, second=second)
    return int(parsed.timestamp())


def timestamp_to_date(stamp: int) -> str:
    '''Return YYYY-MM-DD (local) from a stored epoch timestamp.'''
    return datetime.fromtimestamp(stamp).date().isoformat()


def _task_from_row(row: sqlite3.Row) -> Task:
    return Task(
        id=row['id'],
        task=row['task'],
        description=row['description'],
        timestamp=row['timestamp'],
        sent=row['sent'],
    )
