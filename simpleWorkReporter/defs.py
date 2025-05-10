'''
simpleWorkReporter - definitions.py
---
Central point for application wide settings and other values
to avoid hard coding elements across multiple files
'''
from pathlib import Path
import os

# Configuration File Defaults
CONFIG_FILE_NAME = 'worker.conf'
# Default path is the parent folder of the simpleWorkReporter module
CONFIG_FILE_PATH = Path(
        f'{Path(os.path.dirname(__file__)).parent}/{CONFIG_FILE_NAME}'
    )

# Required CONF_FILE keys for simpleWorkReporter configuration
REQUIRED_CONF_VALUES = [
    'service_port',
    'worker_name',
    'worker_email',
    'manager_name',
    'manager_email',
    'smtp']

# Prompted during setup, otherwise configuration is required
DEFAULT_SERVICE_PORT = 10555
