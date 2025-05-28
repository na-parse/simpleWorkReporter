'''
simpleWorkReporter - mailer.py
Provides mailer routines for sending work summary reports
'''

from . import defs
from . import syslog

import smtplib
import os
import time
from email.utils import formataddr
from datetime import datetime
from typing import Tuple, Optional

from email.mime.text import MIMEText

def _get_send_from(settings: dict) -> str:
    return formataddr((settings["worker_name"],settings["worker_email"]))

def _get_send_to(settings: dict) -> list:
    return [
        formataddr((settings["manager_name"],settings["manager_email"])),
        formataddr((settings["worker_name"],settings["worker_email"]))
    ]

def _get_email_subject(settings: dict, date_range: str) -> str:
    subject = defs.EMAIL_SUBJECT
    return subject.replace(
        "%worker_name%", settings["worker_name"]
    ).replace(
        "%date_range%", date_range
    )

def send_report_email(settings: dict, report_body: str, date_range: str) -> Tuple[bool, Optional[str]]:
    ''' Email the report '''
    email = MIMEText(report_body, 'html')
    SENDFROM = _get_send_from(settings)
    SENDTO = _get_send_to(settings)
    email['From'] = SENDFROM
    email['To'] = f'{", ".join(SENDTO)}'
    email['Subject'] = _get_email_subject(settings,date_range)
    syslog.msg(
        f'Generating email per the following -- \n'
        f'\tFrom: {email["From"]}\n'
        f'\tTo:   {email["To"]}\n'
        f'\tSbjt: {email["Subject"]}\n'
        f'... via SMTP server {settings["smtp"]}:25'
    )
    with smtplib.SMTP(settings["smtp"],25) as server:
        response = server.sendmail(
            SENDFROM,
            SENDTO,
            email.as_string()
        )
        if response:
            return False, response
        else:
            return True, None
