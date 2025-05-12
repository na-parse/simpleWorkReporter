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

    def _get_date_timestamp(self, workDate: str) -> float:
        ''' Internal function to convert webform dates to a timestamp '''
        default_task_time = getattr(defs,'DEFAULT_TASK_TIME','12:00:01')
        current_date = f'{datetime.now():%Y-%m-%d}'
        current_time = f'{datetime.now():%H:%M:%S}'
        workDate = workDate or current_date

        ts_date = f'{current_date} {current_time}' if (
                current_date == workDate
            ) else f'{current_date} {default_task_time}'
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
                    '(taskType, taskSubType, description, datetime, sent) '
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
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f'UPDATE {self._table_name} SET '
                    f'taskType=?, taskSubtype=?, description=?, datetime=?, sent=? WHERE id=?',
                    (taskType,taskSubType,description,timestamp, sent, task_id)
                )
                conn.commit()
        except sqlite3.DatabaseError as e:
            return False, str(e)
        return True, None


    def get_unsent_tasks(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT * FROM {self._table_name}  WHERE sent = 0")
            results = [dict(row) for row in cursor.fetchall()]
            response = []
            for result in results:
                result['date'] = self._get_date(result['datetime'])
                response.append(result)
            syslog.msg(f'Returning {len(response)} unsent tasks.')
            return response


    def get_task(self, task_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT * FROM {self._table_name} WHERE id = ?",(task_id,))
            results = [dict(row) for row in cursor.fetchall()]
            
            if not results:
                return None
            else:
                result = results[0]
                result['date'] = self._get_date(result['datetime'])
                return results[0]

        




        
