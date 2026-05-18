'''Report rendering and SMTP delivery.'''

from __future__ import annotations

import logging
import smtplib
import socket
import sqlite3
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import db
from .settings import WorkerSettings
from .defs import (
    APP_NAME,
    REPORT_NO_ENTRIES_LABEL,
    SMTP_CONNECT_TIMEOUT,
    SUBJECT_TOKEN_DATES,
    SUBJECT_TOKEN_MANAGER,
    SUBJECT_TOKEN_WORKER,
)
from .formatting import description_html


logger = logging.getLogger(__name__)


class MailSendError(RuntimeError):
    '''Raised when SMTP delivery fails.'''


class ReportFlagError(RuntimeError):
    '''Raised when the report was sent but the DB flag update failed.

    The email is already in the recipient's inbox. Re-running send would
    duplicate it because the tasks are still marked unsent. Carries the
    sent count and offending task IDs so the operator can clear them.
    '''

    def __init__(self, count: int, task_ids: list[int], cause: Exception):
        self.count = count
        self.task_ids = task_ids
        self.__cause__ = cause
        super().__init__(
            f'Report sent to recipients ({count} entries) but database '
            f'flagging failed: {cause}. Task IDs left unflagged: {task_ids}. '
            f'Re-running send will duplicate the email; clear via ./swr db.'
        )


def render_report_html(settings: WorkerSettings, tasks: list[db.Task]) -> str:
    '''Render the report HTML used by preview and email delivery.'''
    env = Environment(
        loader=FileSystemLoader(Path(__file__).resolve().parent / 'templates'),
        autoescape=select_autoescape(['html']),
    )
    env.filters['description_html'] = description_html
    template = env.get_template('report_email.html')
    return template.render(
        settings=settings,
        tasks=tasks,
        date_range=db.date_range(tasks),
        host_name=socket.gethostname(),
        app_name=APP_NAME,
    )


def render_subject(
    template: str, settings: WorkerSettings, tasks: list[db.Task]
) -> str:
    '''Substitute %w%, %m%, %d% tokens in a subject template.

    %d% expands to db.date_range() — a single date or 'YYYY-MM-DD - YYYY-MM-DD'
    range — falling back to REPORT_NO_ENTRIES_LABEL when there are no tasks.
    '''
    date_token = db.date_range(tasks) or REPORT_NO_ENTRIES_LABEL
    return (
        template
        .replace(SUBJECT_TOKEN_WORKER, settings.worker_name)
        .replace(SUBJECT_TOKEN_MANAGER, settings.manager_name)
        .replace(SUBJECT_TOKEN_DATES, date_token)
    )


def build_message(settings: WorkerSettings, tasks: list[db.Task]) -> EmailMessage:
    '''Build an email message for the pending report.'''
    message = EmailMessage()
    message['Subject'] = render_subject(settings.report_subject, settings, tasks)
    message['From'] = f'{settings.worker_name} <{settings.worker_email}>'
    message['To'] = f'{settings.manager_name} <{settings.manager_email}>'
    message['Cc'] = settings.worker_email
    message.set_content(_plain_text_report(settings, tasks))
    message.add_alternative(render_report_html(settings, tasks), subtype='html')
    return message


def send_pending_report(
    settings: WorkerSettings | None = None, *, force: bool = False
) -> int:
    '''Send all currently unsent tasks and mark them sent on success.

    Acquires a cross-process mutex via the send_lock table for the entire
    read/send/mark sequence. Concurrent callers see SendLockBusy (surfaced
    as MailSendError to keep the public failure surface unchanged).
    `force=True` bypasses the freshness check so an operator can override
    a stuck/stale lock from the CLI.
    '''
    settings = settings or WorkerSettings()
    try:
        with db.send_lock(force=force):
            return _send_locked(settings)
    except db.SendLockBusy as exc:
        logger.warning('report send refused: %s', exc)
        raise MailSendError(str(exc)) from exc


def _send_locked(settings: WorkerSettings) -> int:
    tasks = db.unsent_tasks()
    if not tasks:
        logger.info('report send skipped; no unsent tasks')
        return 0
    message = build_message(settings, tasks)
    recipients = [
        settings.manager_email,
        settings.worker_email,
    ]
    logger.info(
        'report send starting count=%s smtp_host=%s smtp_port=%s smtp_security=%s auth=%s',
        len(tasks),
        settings.smtp.host,
        settings.smtp.effective_port,
        settings.smtp.security_mode,
        settings.smtp.auth,
    )
    try:
        smtp_class = smtplib.SMTP_SSL if settings.smtp.implicit_tls else smtplib.SMTP
        with smtp_class(
            settings.smtp.host,
            settings.smtp.effective_port,
            timeout=SMTP_CONNECT_TIMEOUT,
        ) as smtp:
            if settings.smtp.starttls:
                logger.debug('smtp starttls upgrade requested')
                smtp.starttls()
            if settings.smtp.auth:
                logger.debug('smtp authentication requested username=%s', settings.smtp.username)
                smtp.login(settings.smtp.username, settings.smtp.password)
            smtp.send_message(message, to_addrs=recipients)
    except (OSError, smtplib.SMTPException) as exc:
        logger.error('report send failed error=%s', exc)
        raise MailSendError(f'Unable to send report: {exc}') from exc
    task_ids = [task.id for task in tasks]
    try:
        db.mark_sent(task_ids)
    except (sqlite3.Error, OSError) as exc:
        # Email already delivered; the DB flag update is what failed. Log
        # loudly so the operator has a record even if the HTTP response is
        # lost, then surface as a distinct error so callers don't treat this
        # as a delivery failure (which would tempt them to retry).
        logger.error(
            'report DELIVERED but flagging failed count=%s task_ids=%s error=%s',
            len(task_ids), task_ids, exc,
        )
        raise ReportFlagError(len(task_ids), task_ids, exc) from exc
    logger.info('report send completed count=%s', len(tasks))
    return len(tasks)


def _plain_text_report(settings: WorkerSettings, tasks: list[db.Task]) -> str:
    lines = [
        f'{APP_NAME} Sender Summary',
        f'Worker: {settings.worker_name} <{settings.worker_email}>',
        f'Manager: {settings.manager_name} <{settings.manager_email}>',
        f'Report Period: {db.date_range(tasks)}',
        '',
    ]
    for task in tasks:
        lines.append(f'{task.display_date} - {task.task}')
        lines.append(task.description)
        lines.append('')
    lines.append(f'Generated by {APP_NAME}.')
    return '\n'.join(lines)
