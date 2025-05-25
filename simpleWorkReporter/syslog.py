'''
simpleWorkReporter / syslog.py
--
Definitions for handling application while console and file logging
This wraps the python logging module around a class.  
'''
import logging
import json
import types
from pathlib import Path

DEFAULT_APP_NAME = 'nb-syslog'
DEFAULT_LOG_PATH = None

# Attempt to load package level defaults for overrides
try: from . import defs
except ModuleNotFoundError: defs = None
app_name = getattr(defs,'PACKAGE_NAME',DEFAULT_APP_NAME)
log_file = getattr(defs,'DEFAULT_LOG_PATH',DEFAULT_LOG_PATH)
console_only = bool(getattr(defs,'LOG_CONSOLE_ONLY',False))
DEBUG = getattr(defs, 'DEBUG', False)

''' Initialize the logger '''
syslog = logging.getLogger(app_name)
syslog.setLevel(logging.DEBUG)
_log_format = "%(asctime)s - %(name)s - %(message)s"
_date_format = "%Y%m%d %H:%M:%S"
_syslog_formatter = logging.Formatter(_log_format, datefmt=_date_format)

''' Setup the console handler '''
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_syslog_formatter)
syslog.addHandler(_console_handler)

''' Establish the file handler variables '''
_file_handler = None

''' Control Variables '''
_activated = False # Prevent adding file handler until 1st log event

def msg(message: str, logger_action = 'msg') -> None:
    global syslog, _activated, log_file
    if log_file is not None and not _activated:
        enable_file_logging()
        _activated = True
    if logger_action == 'msg': logger_func = syslog.info
    if logger_action == 'dbg':  logger_func = syslog.debug
    logger_func(message)

def dbg(message: str) -> None:
    msg(message,'dbg')


def enable_file_logging() -> bool:
    global syslog, log_file, _file_handler, _date_format, _syslog_formatter
    if not log_file:
        return False
    _file_handler = logging.FileHandler(log_file)
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(_syslog_formatter)
    syslog.addHandler(_file_handler)
    return True

def disable_file_logging():
    global syslog, _file_handler
    if _file_handler is not None:
        syslog.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None


def jdump(thisObj,indent: int = 2):
    try: 
        return json.dumps(thisObj,indent=indent)
    except:
        return f'<object_not_JSON_serializable>'

if not DEBUG:
    syslog.disabled = True