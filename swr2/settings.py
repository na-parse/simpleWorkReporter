'''Runtime settings singleton.

One mutable instance per process, mutated in place via update().
ConfigParser is a private serialization detail of this module.
'''

from __future__ import annotations

import configparser
import ipaddress
import logging
import os
import re
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from . import paths
from .credparser import CredParser
from .credparser.errors import DecodeFailure, EncodeFailure, UsageError
from .defs import (
    DEFAULT_SERVICE_PORT,
    EMAIL_SUBJECT_DEFAULT,
    SMTP_SECURITY_ALIASES,
    SMTP_SECURITY_DEFAULT,
    SMTP_SECURITY_DEFAULT_PORTS,
    SMTP_SECURITY_LABELS,
)
from .security import generate_session_secret, hash_passphrase, verify_passphrase


logger = logging.getLogger(__name__)


# =============================================================================
# SMTP security mode
# =============================================================================
# StrEnum so members compare equal to their on-disk string form;
# templates and worker.conf round-trip transparently.

class SmtpSecurity(StrEnum):
    '''SMTP transport security mode.'''

    STARTTLS = 'starttls'
    SMTPS = 'smtps'
    NONE = 'none'

    @property
    def default_port(self) -> int:
        return SMTP_SECURITY_DEFAULT_PORTS[self.value]

    @property
    def label(self) -> str:
        return SMTP_SECURITY_LABELS[self.value]

    @property
    def requires_auth(self) -> bool:
        return self in {SmtpSecurity.STARTTLS, SmtpSecurity.SMTPS}

    @classmethod
    def parse(cls, raw: str) -> 'SmtpSecurity':
        '''Normalize a raw string (including aliases) into a SmtpSecurity.

        Raises ValueError on unrecognized input.
        '''
        normalized = raw.strip().lower().replace('-', '_')
        canonical = SMTP_SECURITY_ALIASES.get(normalized, normalized)
        try:
            return cls(canonical)
        except ValueError as exc:
            raise ValueError(
                'SMTP security mode must be STARTTLS, SMTPS, or None.'
            ) from exc

    @classmethod
    def default(cls) -> 'SmtpSecurity':
        return cls(SMTP_SECURITY_DEFAULT)


# =============================================================================
# SMTP sub-object
# =============================================================================
# credparser holds no plaintext in memory — username/password decode on
# every property access by design.

class SMTPConfig:
    '''SMTP delivery settings with credparser-backed credentials.'''

    def __init__(
        self,
        host: str,
        port: int | None,
        security_mode: SmtpSecurity,
        credentials: CredParser | None,
    ):
        self.host = host
        self.port = port
        self.security_mode = security_mode
        self.credentials = credentials

    @property
    def username(self) -> str:
        if self.credentials is None:
            return ''
        return self.credentials.username or ''

    @property
    def password(self) -> str:
        if self.credentials is None:
            return ''
        return self.credentials.password or ''

    @property
    def effective_port(self) -> int:
        return self.port or self.security_mode.default_port

    @property
    def starttls(self) -> bool:
        return self.security_mode is SmtpSecurity.STARTTLS

    @property
    def implicit_tls(self) -> bool:
        return self.security_mode is SmtpSecurity.SMTPS

    @property
    def auth(self) -> bool:
        '''TLS modes always authenticate; plain SMTP never does.'''
        return self.security_mode.requires_auth


# =============================================================================
# Validation error
# =============================================================================

class ConfigFieldError(ValueError):
    '''Configuration validation failure tied to a specific form field.

    `field` matches the HTML form input name so the web layer can highlight
    the offending input and surface an inline message.
    '''

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


# =============================================================================
# WorkerSettings — the singleton
# =============================================================================

class WorkerSettings:
    '''Runtime settings singleton.

    Loads worker.conf at construction; mutable and reloadable via update().
    On the Flask app it lives at app.settings.
    '''

    worker_name: str
    worker_email: str
    manager_name: str
    manager_email: str
    report_subject: str
    service_port: int
    use_https: bool
    access_hash: str
    session_secret: str
    smtp: SMTPConfig

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or paths.config_path()
        self._load()

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        '''Read worker.conf into self. Overlays the file on built-in defaults.'''
        parser = self._read_parser(self.config_path)
        self.worker_name = parser.get('identity', 'worker_name', fallback='')
        self.worker_email = parser.get('identity', 'worker_email', fallback='')
        self.manager_name = parser.get('identity', 'manager_name', fallback='')
        self.manager_email = parser.get('identity', 'manager_email', fallback='')
        self.report_subject = parser.get(
            'report', 'subject', fallback=EMAIL_SUBJECT_DEFAULT
        ).strip() or EMAIL_SUBJECT_DEFAULT
        self.service_port = parser.getint(
            'service', 'port', fallback=DEFAULT_SERVICE_PORT
        )
        self.use_https = parser.getboolean('service', 'use_https', fallback=False)
        self.access_hash = parser.get('security', 'access_hash', fallback='')
        self.session_secret = parser.get(
            'security', 'session_secret', fallback=''
        )
        smtp_port = _optional_int(parser.get('smtp', 'port', fallback=''))
        smtp_security = SmtpSecurity.parse(
            parser.get('smtp', 'security', fallback=SMTP_SECURITY_DEFAULT)
        )
        credentials = _load_credentials(
            parser.get('smtp', 'credentials', fallback='')
        )
        self.smtp = SMTPConfig(
            host=parser.get('smtp', 'host', fallback=''),
            port=smtp_port,
            security_mode=smtp_security,
            credentials=credentials,
        )

    def reload(self) -> None:
        '''Re-read worker.conf from disk into this instance.'''
        self._load()

    def update(self, **fields) -> None:
        '''Validate, write, and reload in one shot.

        Accepts the kwargs produced by `validate_form`; missing keys retain
        their on-disk value. `access_passphrase` is plaintext and is hashed
        before write.
        '''
        parser = self._read_parser(self.config_path)
        _apply_identity(parser, fields)
        _apply_report(parser, fields)
        _apply_service(parser, fields)
        _apply_smtp(parser, fields)
        _apply_access(parser, fields)
        self._write_parser(parser, self.config_path)
        logger.info('settings updated path=%s', self.config_path)
        self._load()

    # -------------------------------------------------------------------------
    # Predicates / helpers
    # -------------------------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        '''Return whether required configuration has been supplied.'''
        required_strings = [
            self.worker_name,
            self.worker_email,
            self.manager_name,
            self.manager_email,
            self.smtp.host,
        ]
        if not all(value.strip() for value in required_strings):
            return False
        if self.smtp.auth:
            if not (self.smtp.username and self.smtp.password):
                return False
        return True

    def verify_passphrase(self, passphrase: str) -> bool:
        '''Return whether the given passphrase matches the stored hash.'''
        return verify_passphrase(passphrase, self.access_hash)

    # -------------------------------------------------------------------------
    # Pure form validator (web layer)
    # -------------------------------------------------------------------------

    @staticmethod
    def validate_form(
        form: Mapping[str, str], *, existing_credentials: bool
    ) -> tuple[dict | None, dict[str, str]]:
        '''Validate every field of the /config form in one pass.

        Each field validator runs independently so all problems surface on a
        single round trip. `existing_credentials=True` lets a blank password
        mean "keep existing." Returns (update_kwargs, errors); update_kwargs
        is None on failure.
        '''
        errors: dict[str, str] = {}

        worker_name = _validate_required(
            form.get('worker_name', ''), 'worker_name', 'Worker name', errors
        )
        worker_email = _validate_email(
            form.get('worker_email', ''), 'worker_email', 'Worker email', errors
        )
        manager_name = _validate_required(
            form.get('manager_name', ''), 'manager_name', 'Manager name', errors
        )
        manager_email = _validate_email(
            form.get('manager_email', ''), 'manager_email', 'Manager email', errors
        )

        report_subject = form.get('report_subject', '').strip() or EMAIL_SUBJECT_DEFAULT

        try:
            security_mode = SmtpSecurity.parse(form.get('smtp_security', ''))
        except ValueError as exc:
            errors['smtp_security'] = str(exc)
            security_mode = SmtpSecurity.default()

        try:
            port = _required_int(form.get('smtp_port', ''))
        except ValueError as exc:
            errors['smtp_port'] = str(exc)
            port = 0

        try:
            smtp_host = _validate_smtp_host(form.get('smtp_host', ''))
        except ConfigFieldError as exc:
            errors[exc.field] = str(exc)
            smtp_host = ''

        smtp_username = form.get('smtp_username', '').strip()
        smtp_password = form.get('smtp_password', '')
        if security_mode.requires_auth:
            if not smtp_username:
                errors['smtp_username'] = (
                    'SMTP username is required for TLS mail modes.'
                )
            if not smtp_password and not existing_credentials:
                errors['smtp_password'] = (
                    'SMTP password is required for TLS mail modes.'
                )
        else:
            smtp_username = ''
            smtp_password = ''

        if errors:
            return None, errors

        return {
            'worker_name': worker_name,
            'worker_email': worker_email,
            'manager_name': manager_name,
            'manager_email': manager_email,
            'report_subject': report_subject,
            'smtp_host': smtp_host,
            'smtp_security': security_mode,
            'smtp_port': port,
            'smtp_username': smtp_username,
            'smtp_password': smtp_password,
        }, {}

    # -------------------------------------------------------------------------
    # Private serialization
    # -------------------------------------------------------------------------

    @staticmethod
    def _read_parser(path: Path) -> configparser.ConfigParser:
        '''Load the file overlaid on defaults.'''
        parser = _default_parser()
        if path.exists():
            parser.read(path)
        return parser

    @staticmethod
    def _write_parser(parser: configparser.ConfigParser, path: Path) -> None:
        '''Atomically write configuration to disk with mode 0o600.'''
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f'.{path.name}.', dir=str(path.parent), text=True
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as temp_file:
                parser.write(temp_file)
            os.replace(temp_name, path)
            os.chmod(path, 0o600)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


# =============================================================================
# Credential helpers (boundary between credparser and the rest of the app)
# =============================================================================

def build_credentials(username: str, password: str) -> CredParser:
    '''Construct a CredParser, raising ValueError on encode failure.'''
    try:
        return CredParser(username=username, password=password)
    except (EncodeFailure, UsageError) as exc:
        raise ValueError(f'Failed to encode SMTP credentials: {exc}') from exc


def _load_credentials(stored: str) -> CredParser | None:
    '''Build a CredParser from a stored string; returns None on bad input.

    Decode failures are logged so a corrupt config does not crash startup.
    '''
    if not stored:
        return None
    try:
        return CredParser(credentials=stored)
    except (DecodeFailure, UsageError) as exc:
        logger.warning('failed to decode SMTP credentials: %s', exc)
        return None


# =============================================================================
# Internal: section appliers used by update()
# =============================================================================

def _apply_identity(
    parser: configparser.ConfigParser, fields: Mapping[str, object]
) -> None:
    for key in ('worker_name', 'worker_email', 'manager_name', 'manager_email'):
        if key in fields:
            parser['identity'][key] = str(fields[key])


def _apply_report(
    parser: configparser.ConfigParser, fields: Mapping[str, object]
) -> None:
    if 'report_subject' in fields:
        parser['report']['subject'] = str(fields['report_subject'])


def _apply_service(
    parser: configparser.ConfigParser, fields: Mapping[str, object]
) -> None:
    if 'service_port' in fields:
        parser['service']['port'] = str(fields['service_port'])
    if 'use_https' in fields:
        parser['service']['use_https'] = 'on' if fields['use_https'] else 'off'


def _apply_smtp(
    parser: configparser.ConfigParser, fields: Mapping[str, object]
) -> None:
    if 'smtp_host' in fields:
        parser['smtp']['host'] = str(fields['smtp_host'])
    if 'smtp_security' in fields:
        mode = SmtpSecurity.parse(str(fields['smtp_security']))
        parser['smtp']['security'] = mode.value
    if 'smtp_port' in fields:
        parser['smtp']['port'] = str(fields['smtp_port'])
    # Credentials are only rewritten when smtp_security is part of the update.
    if 'smtp_security' in fields:
        if mode.requires_auth:
            username = str(fields.get('smtp_username', ''))
            password = str(fields.get('smtp_password', ''))
            if password:
                new_creds = build_credentials(username, password)
            else:
                # Blank password reuses the stored password under the
                # (possibly new) username.
                existing = _load_credentials(
                    parser['smtp'].get('credentials', '')
                )
                if existing is None:
                    raise ValueError(
                        'smtp_password required when no stored credentials exist'
                    )
                new_creds = build_credentials(username, existing.password)
            parser['smtp']['credentials'] = new_creds.credentials
        else:
            parser['smtp']['credentials'] = ''


def _apply_access(
    parser: configparser.ConfigParser, fields: Mapping[str, object]
) -> None:
    if 'access_passphrase' in fields:
        parser['security']['access_hash'] = hash_passphrase(
            str(fields['access_passphrase'])
        )
        parser['security']['session_secret'] = generate_session_secret()


# =============================================================================
# Internal: parser defaults + field validators
# =============================================================================

def _default_parser() -> configparser.ConfigParser:
    '''Return a config parser populated with expected sections and defaults.'''
    # interpolation=None: the report subject template uses bare %w% / %m% / %d%
    # tokens which BasicInterpolation would treat as malformed %(...)s refs.
    parser = configparser.ConfigParser(interpolation=None)
    parser['identity'] = {
        'worker_name': '',
        'worker_email': '',
        'manager_name': '',
        'manager_email': '',
    }
    parser['report'] = {
        'subject': EMAIL_SUBJECT_DEFAULT,
    }
    parser['smtp'] = {
        'host': '',
        'security': SMTP_SECURITY_DEFAULT,
        'port': str(SMTP_SECURITY_DEFAULT_PORTS[SMTP_SECURITY_DEFAULT]),
        'credentials': '',
    }
    parser['service'] = {
        'port': str(DEFAULT_SERVICE_PORT),
        'use_https': 'off',
    }
    parser['security'] = {
        'access_hash': hash_passphrase(''),
        'session_secret': generate_session_secret(),
    }
    return parser


def _optional_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def _required_int(value: str) -> int:
    value = value.strip()
    if not value:
        raise ValueError('SMTP port is required.')
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError('SMTP port must be numeric.') from exc
    if port < 1 or port > 65535:
        raise ValueError('SMTP port must be between 1 and 65535.')
    return port


# Hostname label: 1-63 chars, alphanumeric, may contain internal hyphens but
# not lead/trail with one. RFC 1123 / 952. Rejects empty labels (`172..16.1.2`)
# which crash the IDNA codec downstream.
_HOSTNAME_LABEL_RE = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$')

# Pragmatic email shape: one local part, one @, one domain with a dot, no
# whitespace. Catches obvious gibberish without trying to be RFC 5322.
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _validate_required(
    raw: str, field: str, label: str, errors: dict[str, str]
) -> str:
    value = raw.strip()
    if not value:
        errors[field] = f'{label} is required.'
    return value


def _validate_email(
    raw: str, field: str, label: str, errors: dict[str, str]
) -> str:
    value = raw.strip()
    if not value:
        errors[field] = f'{label} is required.'
    elif not _EMAIL_RE.match(value):
        errors[field] = f'{label} must look like name@example.com.'
    return value


def _validate_smtp_host(value: str) -> str:
    '''Return a trimmed SMTP host string, raising ConfigFieldError on bad input.'''
    host = value.strip()
    if not host:
        raise ConfigFieldError('smtp_host', 'SMTP server address is required.')
    if len(host) > 253:
        raise ConfigFieldError('smtp_host', 'SMTP server address is too long.')
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    candidate = host[:-1] if host.endswith('.') else host
    labels = candidate.split('.')
    if any(not _HOSTNAME_LABEL_RE.match(label) for label in labels):
        raise ConfigFieldError(
            'smtp_host',
            'SMTP server address must be a valid IP or hostname '
            f'(got: "{host}").',
        )
    return host


