from datetime import datetime
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from simpleworkreporter.db import Task
from simpleworkreporter.defs import EMAIL_SUBJECT_DEFAULT, REPORT_NO_ENTRIES_LABEL
from simpleworkreporter.mail import (
    MailSendError,
    ReportFlagError,
    build_message,
    render_report_html,
    render_subject,
    send_pending_report,
)

from tests.support import TempHomeTestCase, make_settings as _settings


def _epoch(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    '''Local-naive epoch helper so test fixtures stay readable.'''
    return int(datetime(year, month, day, hour, minute).timestamp())


class RenderReportHtmlTests(TempHomeTestCase):
    def test_report_header_summarizes_sender_manager_and_period(self) -> None:
        settings = _settings('none')
        tasks = [
            Task(
                id=1,
                task='Morning work',
                description='Completed the first batch.',
                timestamp=_epoch(2026, 3, 6, 9, 0),
                sent=None,
            ),
            Task(
                id=2,
                task='Follow-up',
                description='Completed the second batch.',
                timestamp=_epoch(2026, 3, 7, 15, 0),
                sent=None,
            ),
        ]

        html = render_report_html(settings, tasks)

        self.assertIn('simpleWorkReporter Sender Summary', html)
        self.assertIn('Worker:', html)
        self.assertIn('Test Worker', html)
        self.assertIn('mailto:worker@example.com', html)
        self.assertIn('Manager:', html)
        self.assertIn('Test Manager', html)
        self.assertIn('mailto:manager@example.com', html)
        self.assertIn('Report Period:', html)
        self.assertIn('2026-03-06 - 2026-03-07', html)

    def test_plain_text_report_summarizes_sender_manager_and_period(self) -> None:
        settings = _settings('none')
        tasks = [
            Task(
                id=1,
                task='Morning work',
                description='Completed the first batch.',
                timestamp=_epoch(2026, 3, 6, 9, 0),
                sent=None,
            )
        ]

        message = build_message(settings, tasks)
        text = message.get_body(preferencelist=('plain',)).get_content()

        self.assertIn('simpleWorkReporter Sender Summary', text)
        self.assertIn('Worker: Test Worker <worker@example.com>', text)
        self.assertIn('Manager: Test Manager <manager@example.com>', text)
        self.assertIn('Report Period: 2026-03-06', text)


class RenderSubjectTests(TempHomeTestCase):
    def test_substitutes_worker_manager_and_date_range(self) -> None:
        settings = _settings('none')
        tasks = [
            Task(id=1, task='A', description='a',
                 timestamp=_epoch(2026, 3, 6, 9, 0), sent=None),
            Task(id=2, task='B', description='b',
                 timestamp=_epoch(2026, 3, 7, 9, 0), sent=None),
        ]
        rendered = render_subject('%w% / %m% / %d%', settings, tasks)
        self.assertEqual(
            'Test Worker / Test Manager / 2026-03-06 - 2026-03-07', rendered
        )

    def test_build_message_subject_uses_configured_template(self) -> None:
        # End-to-end check that build_message reads settings.report_subject
        # and runs it through render_subject. Uses a test-owned template so
        # the assertion isn't coupled to the codebase's default punctuation.
        settings = _settings('none')
        settings.update(report_subject='Report :: %w% :: %d%')
        tasks = [
            Task(id=1, task='A', description='a',
                 timestamp=_epoch(2026, 3, 6, 9, 0), sent=None),
        ]
        message = build_message(settings, tasks)
        self.assertEqual(
            'Report :: Test Worker :: 2026-03-06',
            message['Subject'],
        )

    def test_default_subject_contains_worker_and_date_tokens(self) -> None:
        # Invariant check: the shipped default must reference the worker
        # and the date range so the rendered Subject is meaningful out of
        # the box. Punctuation and word order are intentionally not checked.
        self.assertTrue(EMAIL_SUBJECT_DEFAULT)
        self.assertIn('%w%', EMAIL_SUBJECT_DEFAULT)
        self.assertIn('%d%', EMAIL_SUBJECT_DEFAULT)

    def test_date_token_falls_back_to_no_entries_label(self) -> None:
        settings = _settings('none')
        rendered = render_subject('%d%', settings, [])
        self.assertEqual(REPORT_NO_ENTRIES_LABEL, rendered)


class SendPendingReportTransportTests(TempHomeTestCase):
    def test_starttls_uses_plain_smtp_then_starttls(self) -> None:
        smtp = MagicMock()
        with (
            patch('simpleworkreporter.mail.smtplib.SMTP') as smtp_class,
            patch('simpleworkreporter.mail.smtplib.SMTP_SSL') as smtp_ssl_class,
            patch('simpleworkreporter.mail.db.unsent_tasks', return_value=[_task()]),
            patch('simpleworkreporter.mail.db.mark_sent') as mark_sent,
        ):
            smtp_class.return_value.__enter__.return_value = smtp

            count = send_pending_report(_settings('starttls'))

        self.assertEqual(1, count)
        smtp_class.assert_called_once_with('smtp.example.test', 587, timeout=30)
        smtp_ssl_class.assert_not_called()
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with('worker', 'secret')
        mark_sent.assert_called_once_with([1])

    def test_smtps_uses_implicit_tls_connection(self) -> None:
        smtp = MagicMock()
        with (
            patch('simpleworkreporter.mail.smtplib.SMTP') as smtp_class,
            patch('simpleworkreporter.mail.smtplib.SMTP_SSL') as smtp_ssl_class,
            patch('simpleworkreporter.mail.db.unsent_tasks', return_value=[_task()]),
            patch('simpleworkreporter.mail.db.mark_sent') as mark_sent,
        ):
            smtp_ssl_class.return_value.__enter__.return_value = smtp

            count = send_pending_report(_settings('smtps'))

        self.assertEqual(1, count)
        smtp_ssl_class.assert_called_once_with('smtp.example.test', 465, timeout=30)
        smtp_class.assert_not_called()
        smtp.starttls.assert_not_called()
        smtp.login.assert_called_once_with('worker', 'secret')
        mark_sent.assert_called_once_with([1])

    def test_plain_smtp_does_not_start_tls_or_authenticate(self) -> None:
        smtp = MagicMock()
        with (
            patch('simpleworkreporter.mail.smtplib.SMTP') as smtp_class,
            patch('simpleworkreporter.mail.smtplib.SMTP_SSL') as smtp_ssl_class,
            patch('simpleworkreporter.mail.db.unsent_tasks', return_value=[_task()]),
            patch('simpleworkreporter.mail.db.mark_sent') as mark_sent,
        ):
            smtp_class.return_value.__enter__.return_value = smtp

            count = send_pending_report(_settings('none'))

        self.assertEqual(1, count)
        smtp_class.assert_called_once_with('smtp.example.test', 25, timeout=30)
        smtp_ssl_class.assert_not_called()
        smtp.starttls.assert_not_called()
        smtp.login.assert_not_called()
        mark_sent.assert_called_once_with([1])


def _task() -> Task:
    return Task(
        id=1,
        task='Morning work',
        description='Completed the first batch.',
        timestamp=_epoch(2026, 3, 6, 9, 0),
        sent=None,
    )


class ReportFlagErrorTests(TempHomeTestCase):
    '''Pin the "email delivered but mark_sent failed" branch.

    This is the most operationally dangerous code path — if it broke
    silently the operator would re-send and the manager would get two
    copies. We mock SMTP through to success and force mark_sent to
    raise; the call must surface ReportFlagError (not MailSendError)
    so the CLI can distinguish via exit code 2.
    '''

    def _force_flag_failure(self):
        return patch(
            'simpleworkreporter.mail.db.mark_sent',
            side_effect=sqlite3.OperationalError('disk failure'),
        )

    def test_send_pending_report_raises_report_flag_error_on_mark_failure(self) -> None:
        smtp = MagicMock()
        with (
            patch('simpleworkreporter.mail.smtplib.SMTP') as smtp_class,
            patch('simpleworkreporter.mail.db.unsent_tasks', return_value=[_task()]),
            self._force_flag_failure(),
        ):
            smtp_class.return_value.__enter__.return_value = smtp

            with self.assertRaises(ReportFlagError) as ctx:
                send_pending_report(_settings('starttls'))

        self.assertEqual(1, ctx.exception.count)
        self.assertEqual([1], ctx.exception.task_ids)
        # SMTP actually delivered before the failure.
        smtp.send_message.assert_called_once()

    def test_report_flag_error_is_not_a_mail_send_error(self) -> None:
        # Distinct exception types so callers don't conflate them and retry.
        self.assertFalse(issubclass(ReportFlagError, MailSendError))

    def test_cli_returns_exit_code_2_on_flag_failure(self) -> None:
        from simpleworkreporter.cli.send import main as send_main

        smtp = MagicMock()
        with (
            patch('simpleworkreporter.mail.smtplib.SMTP') as smtp_class,
            patch('simpleworkreporter.mail.db.unsent_tasks', return_value=[_task()]),
            self._force_flag_failure(),
        ):
            smtp_class.return_value.__enter__.return_value = smtp

            rc = send_main([])

        self.assertEqual(2, rc)


if __name__ == '__main__':
    unittest.main()
