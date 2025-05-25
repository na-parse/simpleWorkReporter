'''
simpleWorkReporter - definitions.py
---
Central point for application wide settings and other values
to avoid hard coding elements across multiple files.
'''
from pathlib import Path
import os
import random

# Package Name
PACKAGE_NAME = "simpleWorkReporter"

# DEBUG - Set to any value to enable debugging messages
DEBUG = None

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

# Endpoint routes allowed without authentication
ALLOWED_ENDPOINTS_WITHOUT_AUTH = ['www_login', 'www_logout', 'www_restart']


# Required CONF_FILE keys for simpleWorkReporter configuration
#   Primarily used for building new configuration via setup
REQUIRED_CONF_VALUES = {
    'Service_Port': {
        'default': random.randrange(2000,20000),
        'desc': [
            'Service_Port defines the TCP port the webservice will listen on'
        ]
    },
    'Worker_Name': {
        'default': 'Example Worker',
        'desc': [
            'Worker_Name defines the name of the user tracking work events.',
            '  Used when sending reports to the manager.'
        ]
    },
    'Worker_Email': {
        'default': 'worker-drone@example.com',
        'desc': [
            'Worker_Email defines email for user tracking work events. ',
            '  Reports are sent from, and CCed to this address.'
        ]
    },
    'Manager_Name': {
        'default': 'Manager Name',
        'desc': [
            'Manager_Name defines name of primary recipient for reports. ',
            '  Used to address the manager in the report body.'
        ]
    },
    'Manager_Email': {
        'default': 'manager@example.com',
        'desc': [
            'Manager_Email defines the primary recipient\'s email. ',
            '  Reports are sent and addressed to this address.'
        ]
    },
    'SMTP': {
        'default': 'smtp.example.com',
        'desc': [
            'SMTP assigned the outgoing SMTP server to use for sending daily ',
            '  reports.  Currently only non-TLS port 25 SMTP is supported.'
        ]
    },
    'Access': {
        'default': '',
        'desc': [
            'Access is a SHA256 key of a passphrase used to control access to the',
            '  work reporter console.  Intended to prevent mild mischief, not secure portal.'
        ]
    }
}