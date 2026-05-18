'''Shared test helpers.'''

from __future__ import annotations

import logging
import os
import tempfile
import unittest

from swr2 import db
from swr2.settings import WorkerSettings

# Tests exercise paths that log liberally at INFO. Globally disable INFO and
# below so `python -m unittest` output stays readable. logging.disable beats
# per-logger setLevel, so it survives a CLI test calling configure_logging().
logging.disable(logging.INFO)


# =============================================================================
# Per-test SWR_HOME isolation
# =============================================================================

class TempHomeTestCase(unittest.TestCase):
    '''Point SWR_HOME at a per-test tempdir and initialize a fresh DB.

    Keeps the developer's real ~/.simpleWorkReporter untouched and gives
    each test method its own clean tasks.db (and worker.conf, when the
    test writes one).
    '''

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._prior_home = os.environ.get('SWR_HOME')
        os.environ['SWR_HOME'] = self._tmpdir.name
        db.initialize_database()

    def tearDown(self) -> None:
        if self._prior_home is None:
            os.environ.pop('SWR_HOME', None)
        else:
            os.environ['SWR_HOME'] = self._prior_home
        self._tmpdir.cleanup()

    @property
    def home_dir(self) -> str:
        '''Path to the per-test SWR_HOME (where tasks.db lives).'''
        return self._tmpdir.name


# =============================================================================
# Settings factory shared by mail + web tests
# =============================================================================

_DEFAULT_SMTP_PORTS = {'starttls': 587, 'smtps': 465, 'none': 25}


def make_settings(
    security_mode: str = 'starttls', passphrase: str | None = None
) -> WorkerSettings:
    '''Build a fully-configured WorkerSettings backed by the current SWR_HOME.

    SMTP credentials are inserted only for TLS modes (matches production
    validation). Pass `passphrase` to set the access hash so login tests
    have a known credential.
    '''
    settings = WorkerSettings()
    kwargs: dict = {
        'worker_name': 'Test Worker',
        'worker_email': 'worker@example.com',
        'manager_name': 'Test Manager',
        'manager_email': 'manager@example.com',
        'smtp_host': 'smtp.example.test',
        'smtp_security': security_mode,
        'smtp_port': _DEFAULT_SMTP_PORTS[security_mode],
        'service_port': 5000,
    }
    if security_mode in {'starttls', 'smtps'}:
        kwargs['smtp_username'] = 'worker'
        kwargs['smtp_password'] = 'secret'
    if passphrase is not None:
        kwargs['access_passphrase'] = passphrase
    settings.update(**kwargs)
    return settings


# =============================================================================
# Flask test client helper
# =============================================================================

class WebTestCase(TempHomeTestCase):
    '''TempHomeTestCase + a built Flask app and test_client.

    `self.settings` is the live WorkerSettings bound to `self.app`.
    `self.client` is a Flask test client. `self.authenticate()` flips
    the session cookie directly so route tests don't pay the PBKDF2
    cost on every method — login itself is exercised in test_web_auth.
    '''

    PASSPHRASE = 'test-passphrase'

    def setUp(self) -> None:
        super().setUp()
        # Local import so the support module stays import-safe even if a
        # Flask-less subset of tests is run.
        from swr2.web import create_app

        self.settings = make_settings(passphrase=self.PASSPHRASE)
        self.app = create_app(self.settings)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def authenticate(self, client=None) -> None:
        '''Mark the test client's session as authenticated.'''
        c = client or self.client
        with c.session_transaction() as sess:
            sess['authenticated'] = True
