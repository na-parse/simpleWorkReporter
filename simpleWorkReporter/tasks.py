'''
simpleWorkReporter / tasks.py
--
Task item management routines and classes
'''

from . import defs
from . import syslog
from .errors import *
from .devtools import vardump

from pathlib import Path
from enum import Enum, auto
from typing import Tuple, Optional
from datetime import datetime
import time
import os
import sqlite3

class TaskDatabase():
    ''' 
    TaskDatabase provides the master class definitions for interacting
    with the SimpleWorkReporter database.
    '''

    def __init__(self, db_path: Path = None):
        # Setup the Database values
        self.db_path = db_path or defs.TASKDB_FILE_PATH
        try:
            self._table_name = defs.TASKDB_TASK_TABLE
            self._table_init_sql = defs.TASKDB_TABLESQL
        except AttributeError as e:
            missing = str(e).split("no attribute ")[1].replace("'","")
            raise swrDatabaseError(
                f'Definitions missing attribute for "{missing}"'
            )
        
        result, message = self._validate_db_path(self.db_path)
        if not result:
            raise swrDatabaseError(message)
        self._validated = True
    
    def __str__(self):
        return (f'TaskDatabase(db_path={db_path!r})')

    def _get_date(self,timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    
    def _get_datetime(self,timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    

    def _get_date_timestamp(self, workDate: str = None) -> float:
        ''' Internal function to convert webform dates to a timestamp '''
        default_task_time = getattr(defs,'DEFAULT_TASK_TIME','12:00:01')
        current_date = f'{datetime.now():%Y-%m-%d}'
        current_time = f'{datetime.now():%H:%M:%S}'
        workDate = workDate or current_date

        ts_date = f'{workDate} '
        if current_date == workDate:
            ts_date += f'{current_time}'
        else:
            ts_date += f'{default_task_time}'
        timestamp = datetime.strptime(ts_date, "%Y-%m-%d %H:%M:%S").timestamp()        
        return timestamp

    def _validate_db_path(self, db_path: Path) -> Tuple[bool, Optional[str]]:
        '''
        Validates that the DB file exists and is a valid DB with the
        correct table.  If the file doesn't exist, will invoke create
        command.

        Returns:
            Tuple:
                bool - True/False result of validation,
                msg  - Error message details if validation fails
        '''
        if not os.path.isfile(db_path):
            syslog.msg(f'DB file {db_path} does not exist, creating..')
            self._initialize_db()
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    f"SELECT name FROM sqlite_master "
                    f"WHERE type='table' AND name='{self._table_name}'"
                )
                if cursor.fetchone() is None:
                    error_msg = (
                        f'Specified sqlite DB file is not valid '
                        f'simpleWorkReporter DB: {self.db_path}'
                    )
                    return False, error_msg
        except sqlite3.DatabaseError:
            error_msg = (
                f'Specified file is not a valid simpleWorkReporter '
                f'database file: {self.db_path}'
            )
            return False, error_msg
        return True, None
    
    def _initialize_db(self, db_path: Path = None) -> bool:
        '''
        Initializes a new database at path db_path and is invoked 
        during init if the specified db file doesn't exist
        '''
        if db_path is None:
            db_path = self.db_path
        syslog.dbg(f'Creating DB file {db_path} using TaskDatabase Schema')
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(self._table_init_sql)
                conn.commit()
        except sqlite3.DatabaseError as e:
            error_msg = f'Unexpected error while creating task database: {str(e)}'
            raise swrDatabaseError(error_message)
        return True


    ## PUBLIC METHODS

    def add_task(self, 
        taskType: str,
        taskSubType: str,
        description: str,
        date: str
    ) -> Tuple[bool, Optional[str]]:
        '''
        Add a new task event to the database
        
        By default timestamp will use the current time.
        Returns tuple(result, message) indicating or fail as a bool, and
            message is None or error_message if a failure
        '''
        timestamp = self._get_date_timestamp(date)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f'INSERT INTO {self._table_name} '
                    '(taskType, taskSubType, description, timestamp, sent) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (taskType, taskSubType, description, timestamp, float(0))
                )
                conn.commit()
        except sqlite3.DatabaseError as e:
            return False, str(e)
        return True, None

    def edit_task(self,
        task_id: int,
        taskType: str,
        taskSubType: str,
        description: str,
        date: str,
        sent: float = 0
    ) -> Tuple[bool, Optional[str]]:
        timestamp = self._get_date_timestamp(date)
        sent = float(sent)
        try:
            '''
            Edit an existing task as specified by task_id.
            All fields are expected, except sent (for now)
            IMPL: Current intention is to not allow editing of sent tasks
                  but sent value may need to be mutable in the future.
            '''
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f'UPDATE {self._table_name} SET '
                    f'taskType=?, taskSubtype=?, description=?, timestamp=?, sent=? WHERE id=?',
                    (taskType,taskSubType,description,timestamp, sent, task_id)
                )
                conn.commit()
        except sqlite3.DatabaseError as e:
            return False, str(e)
        return True, None

    def get_tasks(self, unsent_only: bool = False, order_by: str = None) -> list:
        '''
        Returns a list of all unsent task table enteries (dicts)
        '''
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            exec_str = f'SELECT * FROM {self._table_name} '
            if unsent_only: 
                exec_str += 'WHERE sent = 0 '
            if not order_by:
                exec_str += 'ORDER BY id ASC'
            else:
                exec_str += f'ORDER BY {order_by}'
            
            cursor = conn.execute(exec_str)
            results = [dict(row) for row in cursor.fetchall()]
            tasks = []
            for result in results:
                # Generate the display datestring from the REAL value in the DB
                result['date'] = self._get_date(result['timestamp'])
                if result['sent']:
                    result['sentdate'] = self._get_date(result['sent'])
                else:
                    result['sentdate'] = None
                tasks.append(result)
            syslog.msg(f'Returning {len(tasks)} tasks.')
            return tasks

    def get_unsent_tasks(self) -> list:
        tasks = self.get_tasks(unsent_only=True)
        return tasks
    
    def get_unsent_tasks_count(self) -> int:
        ''' Basic call to get unsent task tally when we don't need the values '''
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(id) from {self._table_name} WHERE sent = ?", 
                (0,)
            )
            count = cursor.fetchone()[0]
        syslog.msg(f'Database currently contains {count} unsent tasks.')
        return count


    def get_task(self, task_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT * FROM {self._table_name} WHERE id = ?",(task_id,))
            results = [dict(row) for row in cursor.fetchall()]            
            if not results:
                return None
            else:
                result = results[0]
                result['date'] = self._get_date(result['timestamp'])
                return results[0]

    def delete_task(self, task_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f'DELETE from {self._table_name} WHERE id = ?',
                (task_id,)
            )
            conn.commit()
            rows_deleted = cursor.rowcount

            if not rows_deleted:
                return False
            else:
                return True
    def set_tasks_as_sent(self, tasks: list):
        sent_time = time.time()
        with sqlite3.connect(self.db_path) as conn:
            for task in tasks:
                cursor = conn.execute(
                    f'UPDATE {self._table_name} SET sent = ? WHERE id = ?',
                    (sent_time, task["id"])
                )
                if not cursor.rowcount:
                    raise swrDatabaseError(f'Unable to update task ID {task["id"]} as sent.')
                conn.commit()
                syslog.msg(
                    f'Updated task ID {task["id"]} as sent {sent_time}'
                )
            


    def debug_set_all_sent(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            sent_time = time.time()
            cursor = conn.execute(
                f'UPDATE {self._table_name} SET sent = ? WHERE sent = 0',
                (sent_time,)
            )
            updated_count = cursor.rowcount
            conn.commit()
            syslog.msg(
                f'Updated {updated_count} records with a sent time of '
                f'{sent_time} / {self._get_datetime(sent_time)}'
            )
    

    def debug_clear_sent_time(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            sent_time = 0
            cursor = conn.execute(
                f'UPDATE {self._table_name} SET sent = ?',
                (sent_time,)
            )
            updated_count = cursor.rowcount
            conn.commit()
            syslog.msg(f'Updated {updated_count} records with a sent time of 0')
                



def _get_date_range(tasks: list) -> str:
    ''' 
    Quick format - Take a list of taskdb swr_task items and generate
      a date range for the included items:
        "YYYY-MM-DD" if only a single date, or
        "YYYY-MM-DD - YYYY-MM-DD" if multiple
    '''
    dates = list({ x['date'] for x in tasks })
    dates.sort()
    date_range = f'{dates[0]}' if len(dates) > 0 else ''
    date_range += f' - {dates[-1]}' if len(dates) > 1 else ''
    return date_range
