'''
simpleWorkReporter - definitions.py
---
Central point for application wide settings and other values
to avoid hard coding elements across multiple files.
'''
from pathlib import Path
import os

# Package Name
PACKAGE_NAME = "simpleWorkReporter"

# Prompted during setup, otherwise configuration is required
DEFAULT_SERVICE_PORT = 10555

# Tasks track by Timestamp but prefer Date-only display
# Set a default time for non-current Day Date submissions
DEFAULT_TASK_TIME = '12:00:01'

# Default directory for app data is ../ tracked from these modules
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent

# System console output and logging Defaults
LOG_APP_NAME  = 'simpleWorkReporter'
LOG_FILE_NAME = 'swr_service.log'
LOG_FILE_PATH = DEFAULT_DATA_DIR / LOG_FILE_NAME
LOG_CONSOLE_ONLY = False

# Configuration File Defaults
CONFIG_FILE_NAME = 'worker.conf'
CONFIG_FILE_PATH = DEFAULT_DATA_DIR / CONFIG_FILE_NAME

# Task Database File Definitions
TASKDB_FILE_NAME = 'tasks.db'
TASKDB_FILE_PATH = DEFAULT_DATA_DIR / TASKDB_FILE_NAME

TASKDB_TASK_TABLE = 'swr_tasks'
TASKDB_TABLESQL = f'''
    CREATE TABLE IF NOT EXISTS {TASKDB_TASK_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        taskType TEXT NOT NULL,
        taskSubType TEXT NOT NULL,
        description TEXT,
        timestamp REAL NOT NULL,
        sent REAL NOT NULL DEFAULT 0
    );
'''

# Required CONF_FILE keys for simpleWorkReporter configuration
REQUIRED_CONF_VALUES = [
    'service_port',
    'worker_name',
    'worker_email',
    'manager_name',
    'manager_email',
    'smtp']


