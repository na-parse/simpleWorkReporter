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

# Endpoint routes allowed without authentication
ALLOWED_ENDPOINTS_WITHOUT_AUTH = ['www_login', 'www_logout', 'www_restart', 'www_setauth']

# Builder for sample-worker.conf
SAMPLE_WORKER_CONF = '''\
# Sample Configuration File for the simpleWorkReporter service

# Port defines the TCP Port to listen on - Will use 10555 by default
Port = %service_port%

# Worker_Name and Worker_Email define the user tracking work.  Worker_Email 
#  is added as a recipient for Work Report emails.
Worker_Name = %worker_name%
Worker_Email = %worker_email%

# Manager_Name and Manager_Email define the primary recipient of the report
Manager_Name = %manager_name%
Manager_Email = %manager_email%

# SMTP identifies the SMTP server to use when sending these reports.
#  NOTE: Current version only supports non-TLS port 25 SMTP
#  Future expansions will add support for TLS authenticated services.
SMTP = %smtp%
'''
SAMPLE_WORKER_CONF_VALUES = {
    'service_port': DEFAULT_SERVICE_PORT,
    'worker_name': 'Worker Name',
    'worker_email': 'worker@example.com',
    'manager_name': 'Manager Name',
    'manager_email': 'Manager Email',
    'smtp': 'smtp.example.com',
}

# Access note for conf updates
WORKER_CONF_ACCESS = '''\
# Access key is an SHA256 hash of the password used to secure the app.
# The key is set manually during setup or first access, do not edit
# this value manually.  This section can be removed and the application
# restarted to reset the key.
ACCESS = %access%
'''