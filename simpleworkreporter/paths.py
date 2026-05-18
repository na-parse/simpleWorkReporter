'''Filesystem locations for simpleWorkReporter.'''

from __future__ import annotations

import os
from pathlib import Path

from . import defs


def data_dir() -> Path:
    '''Return the configured application data directory.'''
    override = os.environ.get(defs.ENV_HOME)
    if override:
        return Path(override).expanduser()
    return Path.home() / defs.DEFAULT_DIR_NAME


def config_path() -> Path:
    '''Return the default configuration path.'''
    return data_dir() / defs.CONFIG_FILENAME


def database_path() -> Path:
    '''Return the default SQLite database path.'''
    return data_dir() / defs.DATABASE_FILENAME


def cert_path() -> Path:
    '''Return the default SSL certificate path.'''
    return data_dir() / defs.SSL_CERT_FILENAME


def key_path() -> Path:
    '''Return the default SSL key path.'''
    return data_dir() / defs.SSL_KEY_FILENAME
