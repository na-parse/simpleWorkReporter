'''
simpleWorkReporter - config.py
--
Configuration loader and associated management operations
'''
from . import settings
from dataclasses import dataclass
import os

@dataclass
class swrSettings:
    service_port: int
    worker_name: str
    worker_email: str
    manager_name: str
    manager_email: str
    smtp_relay: str


def load_config_file() -> list:
    ''' 
    Searches for and tries to load the config file.
    Returns the config file as a list of lines
    '''
    if 

