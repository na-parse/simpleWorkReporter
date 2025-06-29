#!/usr/bin/python3
'''
sendReport.py

Provides commandline option to send the work summary report
Script will suppress normal/informational output if it does not detect
  an interactive session on stdout.  This allows easy integration into
  cron type schedulers.
'''

from simpleWorkReporter import SimpleWorkReporter
from simpleWorkReporter import defs

from simpleWorkReporter.devtools import vardump
from simpleWorkReporter import mailer

from simpleWorkReporter.errors import *
from simpleWorkReporter.tasks import _get_date_range
from simpleWorkReporter.app import _get_full_hostname

import sys
import os

appname = defs.PACKAGE_NAME

# Jinja2 Template Setup and Pre-load
from jinja2 import Environment, FileSystemLoader
templates_dir = defs.DEFAULT_DATA_DIR / 'simpleWorkReporter/templates'
jenv = Environment(loader=FileSystemLoader(templates_dir))
report_template = jenv.get_template('report.html')

def ttyout(msg: str = ''):
    ''' Wrapper for print to only stdout if stdout is tty '''
    if sys.stdout.isatty():
        print(msg)

def errout(msg: str):
    ''' Wrapper for printing to stderr for error messages regardless of tty '''
    print(msg,file=sys.stderr)

# =============================================================================
# User Interface Functions
# =============================================================================

def print_header():
    """Print application header with version info."""
    ttyout("=" * 60)
    ttyout("simpleWorkReporter - Send Summary")
    ttyout("=" * 60)
    ttyout()


if __name__ == '__main__':
    try:
        app = SimpleWorkReporter()
    except swrConfigError as e:
        errout(
            f'ERROR: Invalid or missing simpleWorkReporter configuration file.\n'
            f'--\n'
            f'{e}\n\n'
            f'Please run setupService.py to initialize or reset your configuration.'
        )
        exit(1)

    print_header()
    settings = dict(app.settings)
    tasks = app.task_db.get_unsent_tasks()
    date_range = _get_date_range(tasks)
    service_host = _get_full_hostname()

    if not len(tasks):
        errout(f'{appname}: No tasks to send...')
        exit(1)
    # load the email details
    SENDFROM = mailer._get_send_from(settings)
    SENDTO   = mailer._get_send_to(settings)
    SUBJECT  = mailer._get_email_subject(settings, date_range)
    report_body = report_template.render(
        settings=settings,
        date_range=date_range,
        tasks=tasks,
        service_host=service_host
    )
    ttyout(
        f'Sending report containing {len(tasks)} using the following details:\n'
        f'\tFrom: {SENDFROM}\n'
        f'\tTo:   {", ".join(SENDTO)}\n'
        f'\tSubj: {SUBJECT}\n'
        f'... via SMTP server [{settings["smtp"]}]:25'
    )
    result, message = mailer.send_report_email(
        settings,
        report_body,
        date_range
    )
    if not result:
        errout(f'{appname}: Unable to send report email - {message}')
        exit(1)
    else:
        app.task_db.set_tasks_as_sent(tasks)
        ttyout(f'Successfully sent email.')
        exit(0)

