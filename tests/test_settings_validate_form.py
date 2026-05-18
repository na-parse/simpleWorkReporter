'''Pure-function tests for `WorkerSettings.validate_form`.'''

from __future__ import annotations

import unittest

from swr2.settings import WorkerSettings


def _good_form(**overrides) -> dict:
    base = {
        'worker_name': 'Test Worker',
        'worker_email': 'worker@example.com',
        'manager_name': 'Test Manager',
        'manager_email': 'manager@example.com',
        'smtp_host': 'smtp.example.test',
        'smtp_security': 'starttls',
        'smtp_port': '587',
        'smtp_username': 'worker',
        'smtp_password': 'secret',
    }
    base.update(overrides)
    return base


class ValidateFormHappyPathTests(unittest.TestCase):
    def test_returns_normalized_kwargs_and_no_errors(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(), existing_credentials=False
        )
        self.assertEqual({}, errors)
        self.assertIsNotNone(kwargs)
        self.assertEqual('Test Worker', kwargs['worker_name'])
        self.assertEqual('worker@example.com', kwargs['worker_email'])
        self.assertEqual('smtp.example.test', kwargs['smtp_host'])
        self.assertEqual(587, kwargs['smtp_port'])
        self.assertEqual('worker', kwargs['smtp_username'])
        self.assertEqual('secret', kwargs['smtp_password'])

    def test_plain_smtp_strips_credentials(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_security='none', smtp_port='25'),
            existing_credentials=False,
        )
        self.assertEqual({}, errors)
        self.assertEqual('', kwargs['smtp_username'])
        self.assertEqual('', kwargs['smtp_password'])


class ValidateFormIdentityTests(unittest.TestCase):
    '''Coverage for the identity-field validation added during the audit.'''

    def test_blank_worker_name_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(worker_name=''), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('worker_name', errors)

    def test_blank_manager_name_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(manager_name=''), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('manager_name', errors)

    def test_malformed_worker_email_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(worker_email='not-an-email'),
            existing_credentials=False,
        )
        self.assertIsNone(kwargs)
        self.assertIn('worker_email', errors)
        self.assertIn('example.com', errors['worker_email'])

    def test_malformed_manager_email_missing_tld_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(manager_email='manager@localhost'),
            existing_credentials=False,
        )
        self.assertIsNone(kwargs)
        self.assertIn('manager_email', errors)

    def test_whitespace_only_identity_fields_count_as_blank(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(worker_name='   '), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('worker_name', errors)

    def test_all_errors_surface_in_one_pass(self) -> None:
        # All four identity + smtp_host blank → user sees every problem
        # without round-trips.
        form = _good_form(
            worker_name='', worker_email='', manager_name='',
            manager_email='', smtp_host='',
        )
        kwargs, errors = WorkerSettings.validate_form(
            form, existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertEqual(
            {'worker_name', 'worker_email', 'manager_name',
             'manager_email', 'smtp_host'},
            set(errors.keys()),
        )


class ValidateFormSmtpTests(unittest.TestCase):
    def test_unknown_security_mode_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_security='bogus'), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('smtp_security', errors)

    def test_non_numeric_port_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_port='abc'), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('smtp_port', errors)

    def test_out_of_range_port_is_rejected(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_port='70000'), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('smtp_port', errors)

    def test_blank_host_with_empty_label_is_rejected(self) -> None:
        # "172..16.1.2" trips the empty-label guard.
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_host='172..16.1.2'),
            existing_credentials=False,
        )
        self.assertIsNone(kwargs)
        self.assertIn('smtp_host', errors)

    def test_tls_mode_requires_username(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_username=''), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('smtp_username', errors)

    def test_tls_mode_requires_password_when_no_existing_credentials(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_password=''), existing_credentials=False
        )
        self.assertIsNone(kwargs)
        self.assertIn('smtp_password', errors)

    def test_existing_credentials_allow_blank_password(self) -> None:
        kwargs, errors = WorkerSettings.validate_form(
            _good_form(smtp_password=''), existing_credentials=True
        )
        self.assertEqual({}, errors)
        self.assertIsNotNone(kwargs)
        self.assertEqual('', kwargs['smtp_password'])


if __name__ == '__main__':
    unittest.main()
