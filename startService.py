#!/usr/bin/python3
from simpleWorkReporter import SimpleWorkReporter
from simpleWorkReporter.errors import *


if __name__ == '__main__':
    try:
        app = SimpleWorkReporter()
        app.run()
    except swrConfigError as e:
        print(
            f'ERROR: Invalid or missing simpleWorkReporter configuration file.\n'
            f'--\n'
            f'{e}\n\n'
            f'Please run setupService.py to initialize or reset your configuration.'
        )
        exit(1)
