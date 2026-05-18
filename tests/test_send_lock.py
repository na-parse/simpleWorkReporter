'''Tests for the cross-process send mutex (`db.send_lock`).'''

from __future__ import annotations

import sqlite3
import time
import unittest
from pathlib import Path

from simpleworkreporter import db
from simpleworkreporter.defs import SEND_LOCK_STALE_SECONDS

from tests.support import TempHomeTestCase


class SendLockTests(TempHomeTestCase):
    '''Exercise the four acquire paths plus exception-on-release.'''

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _set_acquired_at(self, value: int | None) -> None:
        '''Backdoor the lock row so we can simulate held / stale states.'''
        path = Path(self.home_dir) / 'tasks.db'
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                'UPDATE send_lock SET acquired_at = ? WHERE id = 1', (value,)
            )
            conn.commit()
        finally:
            conn.close()

    def _read_acquired_at(self) -> int | None:
        path = Path(self.home_dir) / 'tasks.db'
        conn = sqlite3.connect(path)
        try:
            row = conn.execute(
                'SELECT acquired_at FROM send_lock WHERE id = 1'
            ).fetchone()
        finally:
            conn.close()
        return row[0]

    # -------------------------------------------------------------------------
    # Tests
    # -------------------------------------------------------------------------

    def test_acquire_and_release_round_trips_cleanly(self) -> None:
        with db.send_lock():
            self.assertIsNotNone(self._read_acquired_at())
        self.assertIsNone(self._read_acquired_at())

    def test_second_acquire_while_held_raises_send_lock_busy(self) -> None:
        with db.send_lock():
            with self.assertRaises(db.SendLockBusy):
                with db.send_lock():
                    self.fail('inner acquire should have raised')

    def test_stale_claim_is_taken_over(self) -> None:
        # Backdate well past the stale window.
        self._set_acquired_at(int(time.time()) - SEND_LOCK_STALE_SECONDS - 60)
        with db.send_lock():
            # Lock row is now claimed under our timestamp, not the stale one.
            self.assertGreater(
                self._read_acquired_at(),
                int(time.time()) - SEND_LOCK_STALE_SECONDS,
            )

    def test_fresh_claim_just_under_threshold_blocks_normal_acquire(self) -> None:
        # One second inside the stale window is still considered fresh.
        self._set_acquired_at(int(time.time()) - SEND_LOCK_STALE_SECONDS + 1)
        with self.assertRaises(db.SendLockBusy):
            with db.send_lock():
                self.fail('acquire should have raised')

    def test_force_acquires_over_fresh_claim(self) -> None:
        # Plant a fresh claim that would normally block.
        self._set_acquired_at(int(time.time()))
        with db.send_lock(force=True):
            self.assertIsNotNone(self._read_acquired_at())
        self.assertIsNone(self._read_acquired_at())

    def test_lock_is_released_when_body_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            with db.send_lock():
                raise RuntimeError('boom')
        self.assertIsNone(self._read_acquired_at())


if __name__ == '__main__':
    unittest.main()
