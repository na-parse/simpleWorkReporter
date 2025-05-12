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
from enum import Enum, auto
from typing import Tuple, Optional


class LoadSwrSettings:
    ''' 
    simpleWorkReporter Configuration Structure
    Init attempts to load configuration file 'worker.conf' from the subdirectory
    of the package by default.
    Specifying a specific config_path Path will load an alternative config file.
    '''

    class UpdateResult(Enum):
        ''' Enums used for handling configuration update result handling '''
        UPDATED = auto()
        NEW_SERVICE_PORT = auto()
        FAILURE = auto()
    
    def __init__(self, config_path: Path = None):
        config_values = self._load_config(config_path)
        try:
            self.service_port = config_values['port']
            self.worker_name = config_values['worker_name']
            self.worker_email = config_values['worker_email']
            self.manager_name = config_values['manager_name']
            self.manager_email = config_values['manager_email']
            self.smtp = config_values['smtp']
            self.config_path = config_values['config_path']
            syslog.msg(f'Loaded configuration values:\n{syslog.jdump(dict(self))}')
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
            f'smtp={self.smtp!r}, config_path={self.config_path!r})'
        )
    
    def __iter__(self):
        yield ("service_port", self.service_port)
        yield ("worker_name", self.worker_name)
        yield ("worker_email", self.worker_email)
        yield ("manager_name", self.manager_name)
        yield ("manager_email", self.manager_email)
        yield ("smtp", self.smtp)
        yield ("config_path", self.config_path)
        

    def update_config(self, 
        service_port: int, worker_name: str, worker_email: str,
        manager_name: str, manager_email: str, smtp: str
    ) -> Tuple['LoadSwrSettings.UpdateResult', Optional[str]]:
        ''' 
        Updates configuration file by loading the raw content of the current 
        config file, and updating the respective lines for each setting, 
        saving the file, and then re-loading the __init__ function to update
        application state with the new config.
        '''
        # Loading the passed values to conf file key structure
        settings = {
            'Port': service_port,
            'Worker_Name': worker_name,
            'Worker_Email': worker_email,
            'Manager_Name': manager_name,
            'Manager_Email': manager_email,
            'SMTP': smtp
        }

        config_lines = self._load_config_lines(self.config_path)
        updated_config_lines = []

        for line in config_lines:
            is_match, key_literal = self._is_config_key(line,settings)
            if is_match:
                # Update the line with the new key/value pair
                line = f'{key_literal} = {settings[key_literal]}'
            updated_config_lines.append(line)

        # Check if the service port is being updated
        new_service_port = not settings['Port'] == self.service_port

        try:
            with open(self.config_path,'w') as f:
                bytes_written = f.write('\n'.join(updated_config_lines) + '\n')
                syslog.dbg(
                    f'Configuration updates written to {self.config_path} '
                    f'({bytes_written} bytes)'
                )
            # Reload settings from updated file
            self.__init__()
            if new_service_port:
                return (self.UpdateResult.NEW_SERVICE_PORT, None)
            else:
                return (self.UpdateResult.UPDATED, None)
        except Exception:
            error_message = (
                f'Configuration update to {self.config_path} failed -- '
                f'{e.__name__} - {str(e)}'
            )
            syslog.dbg(error_message)
            return (self.UpdateResult.FAILURE, error_message)
        
        # Shouldn't get here, raise an internal error for debugging purposes
        raise swrInternalError()


    def _is_config_key(self, line: str, settings: dict) -> bool:
        ''' 
        Parses line for a configuration key and returns
        a tuple of bool, config_key_literal or None depending on match status
        '''
        result = self._parse_config_lines([line])
        if result:
            for config_key in settings:
                if list(result.keys())[0].lower() == config_key.lower():
                    return True, config_key
        return False, None


    def _load_config_lines(self, config_path: Path) -> list:
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

    def _parse_config_lines(self, conf_lines: list) -> dict:
        ''' 
        Accepts config file lines and returns a key/value dict
        Empty lines or lines starting with # are skipped
        Any lines containing data without an '=' will raise a config error
        Settings are assigned as key = value pairs, with key forced to lowercase
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

        return settings

    def _load_config(self, config_path: Path = None) -> dict:
        ''' 
        Load the configuration file data and return the parsed structure
        '''
        # Setup the config_path path using defaults if none specified
        if not config_path:
            config_path = defs.CONFIG_FILE_PATH
        if not os.path.isfile(config_path):
            raise swrConfigError(f'Unable to find configuration file: {config_path}')
        
        # Load the raw line data from the config file and do a basic sanity check
        config_lines = self._load_config_lines(config_path)
        if (
            not config_lines 
            or len(config_lines) < len(defs.REQUIRED_CONF_VALUES)
        ):
            raise swrConfigError(
                f'Incomplete or incorrect file format while reading '
                f'config file: {config_path}'
            )

        # Run the lines through the settings parser
        settings = self._parse_config_lines(config_lines)
        # Append the config file path used for all this as well
        settings['config_path'] = str(config_path)
        return settings
