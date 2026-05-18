'''Flask route coverage.

One file, multiple TestCase classes grouped by route family. All web
tests share `WebTestCase` (in tests.support), which builds a fresh
Flask app against a per-test SWR_HOME and offers `self.authenticate()`
to flip the session cookie directly. The real /login flow is exercised
in `WebAuthTests`; every other route uses the fast helper.
'''

from __future__ import annotations

from unittest.mock import MagicMock, patch

from simpleworkreporter import db

from tests.support import WebTestCase


# =============================================================================
# Auth — exercises the real /login POST and session lifecycle
# =============================================================================

class WebAuthTests(WebTestCase):
    def test_anonymous_request_redirects_to_login(self) -> None:
        rv = self.client.get('/')
        self.assertEqual(302, rv.status_code)
        self.assertIn('/login', rv.headers['Location'])

    def test_anonymous_redirect_preserves_next_target(self) -> None:
        rv = self.client.get('/tasks')
        self.assertIn('next=', rv.headers['Location'])
        self.assertIn('/tasks', rv.headers['Location'])

    def test_login_with_correct_passphrase_redirects_to_dashboard(self) -> None:
        rv = self.client.post('/login', data={'passphrase': self.PASSPHRASE})
        self.assertEqual(302, rv.status_code)
        self.assertTrue(rv.headers['Location'].endswith('/'))

    def test_login_with_wrong_passphrase_returns_401_and_renders_login(self) -> None:
        rv = self.client.post('/login', data={'passphrase': 'wrong'})
        self.assertEqual(401, rv.status_code)
        self.assertIn(b'Passphrase did not match', rv.data)

    def test_login_get_when_authenticated_redirects_to_dashboard(self) -> None:
        self.authenticate()
        rv = self.client.get('/login')
        self.assertEqual(302, rv.status_code)

    def test_logout_clears_session_and_redirects_to_login(self) -> None:
        self.authenticate()
        rv = self.client.post('/logout')
        self.assertEqual(302, rv.status_code)
        # Subsequent request should be anonymous again.
        rv = self.client.get('/')
        self.assertEqual(302, rv.status_code)
        self.assertIn('/login', rv.headers['Location'])

    def test_login_safe_redirect_strips_external_next(self) -> None:
        rv = self.client.post(
            '/login?next=https://evil.example/',
            data={'passphrase': self.PASSPHRASE},
        )
        # Off-host targets fall back to dashboard.
        self.assertTrue(rv.headers['Location'].endswith('/'))


# =============================================================================
# Dashboard — add task / list pending
# =============================================================================

class WebDashboardTests(WebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.authenticate()

    def test_get_dashboard_renders_pending_entries(self) -> None:
        db.add_task('Visible task', 'Visible description')
        rv = self.client.get('/')
        self.assertEqual(200, rv.status_code)
        self.assertIn(b'Visible task', rv.data)

    def test_post_dashboard_adds_a_task(self) -> None:
        rv = self.client.post('/', data={
            'task': 'New entry',
            'description': 'Some description',
        }, follow_redirects=False)
        self.assertEqual(302, rv.status_code)
        tasks = db.unsent_tasks()
        self.assertEqual(1, len(tasks))
        self.assertEqual('New entry', tasks[0].task)

    def test_post_dashboard_with_missing_fields_does_not_create(self) -> None:
        rv = self.client.post('/', data={'task': '', 'description': ''})
        # Re-renders the form with a flash; no task created.
        self.assertEqual(200, rv.status_code)
        self.assertEqual(0, db.count_unsent())

    def test_post_dashboard_with_manual_date_uses_backdated_timestamp(self) -> None:
        rv = self.client.post('/', data={
            'task': 'Backdated',
            'description': 'Was meant for earlier',
            'manual_date': 'on',
            'work_date': '2026-03-01',
        })
        self.assertEqual(302, rv.status_code)
        tasks = db.unsent_tasks()
        self.assertEqual(1, len(tasks))
        self.assertEqual('2026-03-01', tasks[0].display_date)


# =============================================================================
# Task history + edit + delete
# =============================================================================

class WebTaskManagementTests(WebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.authenticate()
        self.task_id = db.add_task('Original task', 'Original description')

    def test_get_tasks_history_lists_entries(self) -> None:
        rv = self.client.get('/tasks')
        self.assertEqual(200, rv.status_code)
        self.assertIn(b'Original task', rv.data)

    def test_get_edit_form_renders_task_data(self) -> None:
        rv = self.client.get(f'/tasks/{self.task_id}/edit')
        self.assertEqual(200, rv.status_code)
        self.assertIn(b'Original task', rv.data)

    def test_get_edit_for_missing_task_redirects_to_dashboard(self) -> None:
        rv = self.client.get('/tasks/9999/edit')
        self.assertEqual(302, rv.status_code)

    def test_post_edit_updates_task(self) -> None:
        rv = self.client.post(f'/tasks/{self.task_id}/edit', data={
            'task': 'Updated task',
            'description': 'Updated description',
            'work_date': '2026-03-10',
        })
        self.assertEqual(302, rv.status_code)
        task = db.get_task(self.task_id)
        assert task is not None
        self.assertEqual('Updated task', task.task)
        self.assertEqual('Updated description', task.description)

    def test_post_edit_with_missing_field_does_not_update(self) -> None:
        self.client.post(f'/tasks/{self.task_id}/edit', data={
            'task': '',
            'description': 'still here',
            'work_date': '2026-03-10',
        })
        task = db.get_task(self.task_id)
        assert task is not None
        self.assertEqual('Original task', task.task)

    def test_post_delete_removes_task(self) -> None:
        rv = self.client.post(f'/tasks/{self.task_id}/delete')
        self.assertEqual(302, rv.status_code)
        self.assertIsNone(db.get_task(self.task_id))


# =============================================================================
# Config
# =============================================================================

class WebConfigTests(WebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.authenticate()

    def test_get_config_renders_current_values(self) -> None:
        rv = self.client.get('/config')
        self.assertEqual(200, rv.status_code)
        self.assertIn(b'worker@example.com', rv.data)
        self.assertIn(b'smtp.example.test', rv.data)

    def test_get_config_shows_swr_setup_breadcrumb(self) -> None:
        # Notice steering users to the CLI for port / use_https.
        rv = self.client.get('/config')
        self.assertIn(b'./swr setup', rv.data)

    def test_post_config_with_valid_data_persists(self) -> None:
        rv = self.client.post('/config', data={
            'worker_name': 'Changed Worker',
            'worker_email': 'changed@example.com',
            'manager_name': 'Test Manager',
            'manager_email': 'manager@example.com',
            'smtp_host': 'mail.example.org',
            'smtp_security': 'starttls',
            'smtp_port': '587',
            'smtp_username': 'worker',
            'smtp_password': '',  # blank reuses stored credential
        })
        self.assertEqual(302, rv.status_code)
        self.assertEqual('Changed Worker', self.settings.worker_name)
        self.assertEqual('mail.example.org', self.settings.smtp.host)

    def test_post_config_with_bad_email_re_renders_form(self) -> None:
        rv = self.client.post('/config', data={
            'worker_name': 'W',
            'worker_email': 'not-an-email',
            'manager_name': 'M',
            'manager_email': 'm@example.com',
            'smtp_host': 'smtp.example.test',
            'smtp_security': 'starttls',
            'smtp_port': '587',
            'smtp_username': 'worker',
            'smtp_password': 's',
        })
        self.assertEqual(200, rv.status_code)
        # Invalid field marker + the bad value echoed back.
        self.assertIn(b'is-invalid', rv.data)
        self.assertIn(b'not-an-email', rv.data)
        # Settings were not persisted.
        self.assertEqual('worker@example.com', self.settings.worker_email)


# =============================================================================
# /send — preview + delivery
# =============================================================================

class WebSendTests(WebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.authenticate()

    def test_get_send_with_no_pending_tasks_redirects(self) -> None:
        rv = self.client.get('/send')
        self.assertEqual(302, rv.status_code)

    def test_get_send_with_pending_tasks_renders_preview(self) -> None:
        db.add_task('Preview', 'Preview body')
        rv = self.client.get('/send')
        self.assertEqual(200, rv.status_code)
        self.assertIn(b'Preview', rv.data)

    def test_post_send_happy_path_marks_tasks_sent(self) -> None:
        tid = db.add_task('Outgoing', 'Outgoing body')
        smtp = MagicMock()
        with patch('simpleworkreporter.mail.smtplib.SMTP') as smtp_class:
            smtp_class.return_value.__enter__.return_value = smtp
            rv = self.client.post('/send')
        self.assertEqual(302, rv.status_code)
        smtp.send_message.assert_called_once()
        task = db.get_task(tid)
        assert task is not None
        self.assertTrue(task.is_sent)

    def test_post_send_surfaces_mail_send_error_as_flash(self) -> None:
        db.add_task('Outgoing', 'body')
        with patch(
            'simpleworkreporter.mail.smtplib.SMTP',
            side_effect=OSError('connection refused'),
        ):
            rv = self.client.post('/send', follow_redirects=False)
        # Route re-renders the send page (no redirect) with the error flash.
        self.assertEqual(200, rv.status_code)
        self.assertIn(b'connection refused', rv.data)
        # Task remains unsent.
        self.assertEqual(1, db.count_unsent())


# =============================================================================
# Theme picker
# =============================================================================

class WebThemeTests(WebTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.authenticate()

    def test_get_theme_page_renders(self) -> None:
        rv = self.client.get('/theme')
        self.assertEqual(200, rv.status_code)

    def test_post_known_theme_sets_session_cookie(self) -> None:
        rv = self.client.post('/theme', data={'theme': 'dark'})
        self.assertEqual(302, rv.status_code)
        with self.client.session_transaction() as sess:
            self.assertEqual('dark', sess['theme'])

    def test_post_unknown_theme_is_ignored(self) -> None:
        self.client.post('/theme', data={'theme': 'lol-no-such-theme'})
        with self.client.session_transaction() as sess:
            self.assertNotIn('theme', sess)


if __name__ == '__main__':
    import unittest
    unittest.main()
