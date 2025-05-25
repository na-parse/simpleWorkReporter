#!/usr/bin/python3
from simpleWorkReporter import config
from simpleWorkReporter import defs
from simpleWorkReporter.errors import *
from simpleWorkReporter import syslog


import os
from enum import Enum, auto
from pathlib import Path

config_path = defs.CONFIG_FILE_PATH

class RunMode(Enum):
    INIT = auto()
    UPDATE = auto()
    RESET = auto()


def query_setup_value(key: str, value: dict, default: str = None, update = False):
    '''
    Uses the supplied setup key and value details to request user input.
    '''
    print()
    for line in value['desc']:  print(f'# {line}')
    print()
    default = default or value["default"]
    if key.lower() == 'access':
        response = input(f'{key} = ')
    else:
        response = input(f'{key} [{default}] = ')
    if not response:
        if key.lower() == 'access':
            if not update:
                # Empty password
                response = ''
                msg__no_password()
            else:
                # Set to None to flag for no-update/change
                response = None
        else: 
            print(f'  Using default value: {default}')
            response = default
    return response

def msg_intro():
    print(f'simpleWorkReporter - Setup\n--')

def msg__init_intro(config_path):
    print(f'Creating a new simpleWorkReporter configuration file:\n  - {config_path}')

def msg__no_password():
    print(
        f'WARNING:\n'
        f'  You have skipped setting a passphrase to protect the portal.\n'
        f'  Submit an empty password field when prompted for a password.\n'
    )

def wizard__verify_settings(settings: dict, update: bool = False):
    print()
    print(
        f'Verify your simpleWorkReporter settings:\n'
        f'---------------------------------------\n'
    )
    for k, v in settings.items():
        if k == 'access' and v is None:
            v = '<no change>'
        print(f'{k.rjust(20)} = {v}')
    print()
    response = input(f'Commit settings? (y/N/q) > ')
    if not response or response[0].lower() not in 'yq':
        return False
    if response[0].lower() == 'y':
        return True
    else:
        print(f'Aborting setup...')
        exit(1)

def wizard__collect_settings(config_path: Path, settings: dict = {}, update: bool = False):
    commit = False
    while not commit:
        for k, v in defs.REQUIRED_CONF_VALUES.items():
            settings[k.lower()] = query_setup_value(
                k, v, settings.get(k.lower(),''), update=update
            )
        if wizard__verify_settings(settings):
            commit = True
    if update:
        print(f'- Updating settings in {config_path}...')
        config.update_config(config_path,
            service_port = settings['service_port'],
            worker_name = settings['worker_name'],
            worker_email = settings['worker_email'],
            manager_name = settings['manager_name'],
            manager_email = settings['manager_email'],
            smtp = settings['smtp'],
            access = settings['access']
        )
    else:
        print(f'- Saving settings to {config_path}...')
        config.create_config_file(config_path, settings)


def wizard__init(config_path: Path, settings = {}):
    msg__init_intro(config_path)
    wizard__collect_settings(config_path, settings)
    print(f'Setup completed, service can now be started by running startService.py')
    exit(0)

def wizard__update(config_path: Path, settings: dict = {}):
    print(
        f'Updating the existing simpleWorkReporter configuration.\n'
        f'Existing values will be preserved if left blank.'
    )
    wizard__collect_settings(config_path, settings, update=True)
    print(f'Update completed. Service should be restarted now for updates to take effect.')
    exit(0)


def wizard__reset(config_path: Path, error: str, settings: dict = {}):
    print(
        f'Configuration file {config_path} is invalid:\n'
        f' - {error}\n\n'
        f'Remove the corrupt file and reinitialize your configuration?'
    )
    response = input(f'Continue? (y/N) > ')
    if not response or not response[0].lower() == 'y':
        print(f'Aborting...')
        exit(1)
    else:
        os.remove(config_path)
        print(f'Removed the previous configuration file, proceeding with new setup...\n')
        wizard__init(config_path, settings)
        


if __name__ == '__main__':
    msg_intro()
    run_mode = RunMode.INIT   # setting a default mode as fallback
    
    if not os.path.isfile(config_path):
        run_mode = RunMode.INIT  # No file, create new
    elif os.path.isfile(config_path):
        try:
            settings = config._load_config(config_path)
            run_mode = RunMode.UPDATE
        except swrConfigError as e:
            settings = config._load_config(config_path, allow_partial = True)
            run_mode = RunMode.RESET
            error = f'{e}'
    
    if run_mode == RunMode.INIT:
        wizard__init(config_path)
    if run_mode == RunMode.UPDATE:
        wizard__update(config_path, settings)
    if run_mode == RunMode.RESET:
        wizard__reset(config_path, error, settings)
