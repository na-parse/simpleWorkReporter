'''CRUD coverage for simpleworkreporter.db.'''

from __future__ import annotations

from datetime import datetime
import time
import unittest

from simpleworkreporter import db
from simpleworkreporter.defs import DEFAULT_BACKDATED_TIME

from tests.support import TempHomeTestCase


def _epoch(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, 12, 0, 0).timestamp())


class CrudTests(TempHomeTestCase):
    def test_add_and_get_round_trip(self) -> None:
        tid = db.add_task('Morning', 'Did stuff', timestamp=_epoch(2026, 3, 6))
        task = db.get_task(tid)
        assert task is not None
        self.assertEqual('Morning', task.task)
        self.assertEqual('Did stuff', task.description)
        self.assertEqual(_epoch(2026, 3, 6), task.timestamp)
        self.assertIsNone(task.sent)
        self.assertFalse(task.is_sent)

    def test_add_task_strips_whitespace(self) -> None:
        tid = db.add_task('  Trimmed  ', '\n leading-and-trailing  \n')
        task = db.get_task(tid)
        assert task is not None
        self.assertEqual('Trimmed', task.task)
        self.assertEqual('leading-and-trailing', task.description)

    def test_get_task_returns_none_for_missing_id(self) -> None:
        self.assertIsNone(db.get_task(9999))

    def test_update_task_changes_fields(self) -> None:
        tid = db.add_task('Old', 'Old description')
        db.update_task(tid, 'New', 'New description', _epoch(2026, 3, 7))
        task = db.get_task(tid)
        assert task is not None
        self.assertEqual('New', task.task)
        self.assertEqual('New description', task.description)
        self.assertEqual(_epoch(2026, 3, 7), task.timestamp)

    def test_delete_task_removes_row(self) -> None:
        tid = db.add_task('To delete', 'Bye')
        db.delete_task(tid)
        self.assertIsNone(db.get_task(tid))

    def test_delete_all_tasks_clears_table(self) -> None:
        db.add_task('A', 'a')
        db.add_task('B', 'b')
        db.delete_all_tasks()
        self.assertEqual([], db.all_tasks())

    def test_unsent_tasks_are_oldest_first(self) -> None:
        db.add_task('Newer', 'n', timestamp=_epoch(2026, 3, 8))
        db.add_task('Older', 'o', timestamp=_epoch(2026, 3, 6))
        ordered = [t.task for t in db.unsent_tasks()]
        self.assertEqual(['Older', 'Newer'], ordered)

    def test_all_tasks_are_newest_first(self) -> None:
        db.add_task('Older', 'o', timestamp=_epoch(2026, 3, 6))
        db.add_task('Newer', 'n', timestamp=_epoch(2026, 3, 8))
        ordered = [t.task for t in db.all_tasks()]
        self.assertEqual(['Newer', 'Older'], ordered)

    def test_count_unsent_excludes_sent_rows(self) -> None:
        a = db.add_task('A', 'a')
        db.add_task('B', 'b')
        db.mark_sent([a])
        self.assertEqual(1, db.count_unsent())

    def test_mark_sent_only_flags_specified_unsent_ids(self) -> None:
        a = db.add_task('A', 'a')
        b = db.add_task('B', 'b')
        c = db.add_task('C', 'c')
        db.mark_sent([a, c])
        sent = {t.id: t.is_sent for t in db.all_tasks()}
        self.assertTrue(sent[a])
        self.assertFalse(sent[b])
        self.assertTrue(sent[c])

    def test_mark_sent_is_noop_for_empty_list(self) -> None:
        a = db.add_task('A', 'a')
        # Must not crash and must not flag the existing row.
        db.mark_sent([])
        task = db.get_task(a)
        assert task is not None
        self.assertFalse(task.is_sent)

    def test_mark_sent_does_not_overwrite_existing_sent_timestamp(self) -> None:
        # Re-flagging an already-sent task must not change its sent stamp.
        a = db.add_task('A', 'a')
        db.mark_sent([a], sent_timestamp=1000)
        db.mark_sent([a], sent_timestamp=2000)
        task = db.get_task(a)
        assert task is not None
        self.assertEqual(1000, task.sent)

    def test_add_task_record_accepts_explicit_sent(self) -> None:
        tid = db.add_task_record('A', 'a', _epoch(2026, 3, 6), sent=12345)
        task = db.get_task(tid)
        assert task is not None
        self.assertEqual(12345, task.sent)
        self.assertTrue(task.is_sent)


class DateHelperTests(unittest.TestCase):
    '''Pure helpers — no DB needed.'''

    def test_date_range_empty(self) -> None:
        self.assertEqual('', db.date_range([]))

    def test_date_range_single_date(self) -> None:
        tasks = [
            db.Task(id=1, task='T', description='d',
                    timestamp=_epoch(2026, 3, 6), sent=None),
        ]
        self.assertEqual('2026-03-06', db.date_range(tasks))

    def test_date_range_spans_collapse_to_min_max(self) -> None:
        tasks = [
            db.Task(id=1, task='A', description='a',
                    timestamp=_epoch(2026, 3, 6), sent=None),
            db.Task(id=2, task='B', description='b',
                    timestamp=_epoch(2026, 3, 9), sent=None),
            db.Task(id=3, task='C', description='c',
                    timestamp=_epoch(2026, 3, 7), sent=None),
        ]
        self.assertEqual('2026-03-06 - 2026-03-09', db.date_range(tasks))

    def test_date_to_timestamp_today_returns_now(self) -> None:
        before = int(time.time())
        stamp = db.date_to_timestamp(datetime.now().date().isoformat())
        after = int(time.time())
        self.assertTrue(before <= stamp <= after)

    def test_date_to_timestamp_backdated_uses_canonical_time(self) -> None:
        stamp = db.date_to_timestamp('2026-03-06')
        parsed = datetime.fromtimestamp(stamp)
        self.assertEqual((2026, 3, 6), (parsed.year, parsed.month, parsed.day))
        h, m, s = DEFAULT_BACKDATED_TIME
        self.assertEqual((h, m, s), (parsed.hour, parsed.minute, parsed.second))

    def test_date_to_timestamp_empty_returns_now(self) -> None:
        before = int(time.time())
        stamp = db.date_to_timestamp('')
        after = int(time.time())
        self.assertTrue(before <= stamp <= after)


if __name__ == '__main__':
    unittest.main()
