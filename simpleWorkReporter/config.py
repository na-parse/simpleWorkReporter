'''
simpleWorkReporter - config.py
--
Configuration loader and associated management operations
'''
from . import defs
from . import syslog
from .devtools import vardump
from .errors import *


from pathlib import Path
import os
import hashlib
from enum import Enum, auto
from typing import Tuple, Optional
from datetime import datetime

class UpdateResult(Enum):
    ''' Enums used for handling configuration update result handling '''
    UPDATED = auto()
    NEW_SERVICE_PORT = auto()
    FAILURE = auto()


class LoadSwrSettings:
    ''' 
    simpleWorkReporter Configuration Structure
    Init attempts to load configuration file 'worker.conf' from the subdirectory
    of the package by default.
    Specifying a specific config_path Path will load an alternative config file.
    '''
    def __init__(self, config_path: Path = None):
        config_values = _load_config(config_path)
        try:
            self.service_port = config_values['service_port']
            self.worker_name = config_values['worker_name']
            self.worker_email = config_values['worker_email']
            self.manager_name = config_values['manager_name']
            self.manager_email = config_values['manager_email']
            self.smtp = config_values['smtp']
            self.access = config_values.get('access')
            self.config_path = config_values['config_path']
            syslog.dbg(f'Loaded configuration values:\n{syslog.jdump(dict(self))}')
        except KeyError as e:
            msg = f'Configuration missing required value: \'{str(e.args[0]).upper()}\''
            raise swrConfigError(msg) from None

    def __repr__(self):
        return f'LoadSwrSettings(config_path={self.config_path!r})'
    
    def __str__(self):
        return (
            f'LoadSwrSettings(service_port={self.service_port!r}, '
            f'worker_name={self.worker_name!r}, worker_email={self.worker_email!r}, '
            f'manager_name={self.manager_name!r}, manager_email={self.manager_email!r}, '
            f'smtp={self.smtp!r}, access={self.access!r}, config_path={self.config_path!r})'
        )
    
    def __iter__(self):
        yield ("service_port", self.service_port)
        yield ("worker_name", self.worker_name)
        yield ("worker_email", self.worker_email)
        yield ("manager_name", self.manager_name)
        yield ("manager_email", self.manager_email)
        yield ("smtp", self.smtp)
        yield ("access", self.access)
        yield ("config_path", self.config_path)

    def is_pass_valid(self, password: str) -> bool:
        ''' Validate that supplied password hash matches access key '''
        if self.access == _hash_password(password):
            return True
        return False

    def update_config(self, 
        service_port: int, worker_name: str, worker_email: str,
        manager_name: str, manager_email: str, smtp: str, access: str = None
    ) -> Tuple['UpdateResult', Optional[str]]:
        '''
        Class internal wrapper to general config file update with additional
        logic to handle instantiated class change components
        '''
        update_config(self.config_path, service_port, 
            worker_name, worker_email, manager_name, manager_email, 
            smtp, access)
        
        # Check if the service port is being updated
        new_service_port = not service_port == self.service_port
        # Reload settings from updated file
        self.__init__()
        if new_service_port:
            return (UpdateResult.NEW_SERVICE_PORT, None)
        else:
            return (UpdateResult.UPDATED, None)
        return (UpdateResult.FAILURE, error_message)


def _hash_password(password: str, encode_method: str = 'utf-8') -> str:
    '''
    Returns a SHA256 hexdigest hash of the supplied password
    Uses a salt to allow 'blank' passwords
    '''
    sha256 = hashlib.sha256()
    password = f'0x9c87l1p#9540*D.d1Ad9{password}'
    sha256.update(password.encode(encode_method))
    return sha256.hexdigest()



def update_config(config_path: Path, service_port: int, 
                  worker_name: str, worker_email: str,
                  manager_name: str, manager_email: str, 
                  smtp: str, access: str = None) -> bool:
    ''' 
    Updates configuration file by loading the raw content of the current 
    config file, and updating the respective lines for each setting, 
    saving the file, and then re-loading the __init__ function to update
    application state with the new config.
    '''

    # Loading the passed values to conf file key structure
    settings = {
        'Service_Port': service_port,
        'Worker_Name': worker_name,
        'Worker_Email': worker_email,
        'Manager_Name': manager_name,
        'Manager_Email': manager_email,
        'SMTP': smtp
    }
    # Convert access to a hash if it was set
    if access is not None: 
        access = _hash_password(access)
        settings['Access'] = access

    syslog.dbg(f'Updating configuration file {config_path}')
    config_lines = _load_config_lines(config_path)
    updated_config_lines = []
    matched_keys = set()
    for line in config_lines:
        is_match, key_literal = _is_config_key(line,settings)
        if is_match and settings[key_literal] is not None:
            # Update the line with the new key/value pair
            line = f'{key_literal} = {settings[key_literal]}'
            matched_keys.add(key_literal)
            syslog.dbg(f'Updating config values for {key_literal}')
        updated_config_lines.append(line)
    
    try:    
        with open(config_path,'w') as f:
            bytes_written = f.write('\n'.join(updated_config_lines) + '\n')
            syslog.dbg(
                f'Configuration updates written to {config_path} '
                f'({bytes_written} bytes)'
            )
    except Exception:
        error_message = (
            f'Configuration update to {config_path} failed -- '
            f'{e.__name__} - {str(e)}'
        )
        syslog.dbg(error_message)
    return True


def _is_config_key(line: str, settings: dict) -> bool:
    ''' 
    Parses line for a configuration key and returns
    a tuple of bool, config_key_literal or None depending on match status
    '''
    result = _parse_config_lines([line],allow_partial=True)
    if result:
        for config_key in settings:
            if list(result.keys())[0].lower() == config_key.lower():
                return True, config_key
    return False, None


def _load_config_lines(config_path: Path) -> list:
    '''
    Load the raw configuration file line data. Returns a list of lines.
    '''
    try:
        with open(config_path,'r') as f:
            lines = [ line.strip() for line in f.readlines() ]
    except Exception as e:
        raise swrConfigError(
            f'Encountered error while reading configuration file: '
            f'{config_path}\n - {e.__name__} {e}'
        )
    return lines


def _parse_config_lines(conf_lines: list, allow_partial: bool = False) -> dict:
    ''' 
    Accepts config file lines and returns a key/value dict.  Empty lines or lines
    starting with a # are considered comments and skipped.
    Any lines containing data without an '=' will raise a config error.
    Settings are assigned as key = value pairs, with key forced to lowercase
    Missing any values defined in defs.REQUIRED_CONF_VALUES is considered a
    fatal error.
    Setting allow_partial will permit an incomplete return for valid conf values.
    '''
    settings = {}
    bad_lines = {}
    for line_num, line in enumerate(conf_lines,1):
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=',1)
            settings[key.strip().lower()] = value.strip()
            continue
        # If we get here, there's some weird garbage in the config
        bad_lines[line_num] = line
    
    # Error check for bad data
    if bad_lines:
        print(f'ERROR: Invalid/Corrupt data in configuration.\n---\n')
        for bad_line in bad_lines: 
            print(f'[{str(bad_line).rjust(3)}]: {bad_lines[bad_line]}')
        raise swrConfigError('Invalid configuration data')

    # Validate all expected settings are found
    missing_keys = [ k for k in defs.REQUIRED_CONF_VALUES if not k.lower() in settings ]
    if missing_keys and not allow_partial:
        raise swrConfigError(f'Configuration missing required key values: {missing_keys}')
    
    return settings


def _load_config(config_path: Path = None, allow_partial: bool = False) -> dict:
    ''' 
    Load the configuration file data and return the parsed structure

    args:
        config_path - path to config file.  Will use defs.CONFIG_FILE_PATH
                      if left empty
        allow_partial - used for internal services, will return any valid
                        settings found in config file without errors for
                        missing or partial values.

    By default, expects to find key values for all config items setup in the 
      defs.REQUIRED_CONF_VALUES structure.
    '''
    # Setup the config_path path using defaults if none specified
    if not config_path:
        config_path = defs.CONFIG_FILE_PATH
    if not os.path.isfile(config_path):
        raise swrConfigError(f'Unable to find configuration file: {config_path}')
    
    # Load the raw line data from the config file and do a basic sanity check
    config_lines = _load_config_lines(config_path)
    if (
        not config_lines 
        or len(config_lines) < len(defs.REQUIRED_CONF_VALUES)
    ):
        raise swrConfigError(
            f'Incomplete or incorrect file format while reading '
            f'config file: {config_path}'
        )

    # Run the lines through the settings parser
    settings = _parse_config_lines(config_lines, allow_partial=allow_partial)
    # Append the config file path used for all this as well
    settings['config_path'] = str(config_path)
    return settings

def create_config_file(config_path: Path, settings: dict):
    '''
    Creates a new configuration file based around the supplied settings
    and the associated values found in defs.REQUIRED_CONF_VALUES.
    
    The config value's description is written as a comment before the
    key assignment line.  All expected values must be found or an
    exception is raised.
    '''
    # Initialize config_lines list with header line
    config_lines = [f'# worker.conf - simpleWorkReporter config file '
                    f'- {datetime.now():%Y-%m-%d %H:%M}', 
                    f'' ]
    # First convert the access value to a password hash
    settings['access'] = _hash_password(settings['access'])
    for setting, details in defs.REQUIRED_CONF_VALUES.items():
        try:
            for line in details['desc']:
                config_lines.append(f'# {line}')
            value = settings[setting.lower()]
            config_lines.append(f'{setting} = {value}')
            config_lines.append(f'')
        except KeyError as e:
            raise swrConfigError(f'Missing settings value for {setting}')
    with open(config_path,'w') as f:
        bytes_written = f.write("\n".join(config_lines) + "\n")
        syslog.dbg(f'Wrote {bytes_written} bytes to config file: {config_path}')


