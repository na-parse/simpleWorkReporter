'''Interactive setup command.'''

from __future__ import annotations

import argparse
import sys
from typing import Any

from .. import paths
from ..defs import APP_NAME, DEFAULT_SERVICE_PORT
from ..certs import is_ssl_configured
from ..settings import SmtpSecurity, WorkerSettings, build_credentials
from .ui import TerminalUI


def main(argv: list[str] | None = None) -> int:
    '''Run the setup wizard.'''
    parser = argparse.ArgumentParser(prog='swr setup')
    parser.parse_args(argv)
    run_setup()
    return 0


def run_setup() -> None:
    ui = TerminalUI()
    try:
        _run_setup(ui)
    except KeyboardInterrupt as exc:
        print()
        ui.warning('Setup interrupted.')
        raise SystemExit(1) from exc
    except EOFError as exc:
        print()
        ui.warning('Setup input ended unexpectedly.')
        raise SystemExit(1) from exc


def _run_setup(ui: TerminalUI) -> None:
    ui.header(f'{APP_NAME} setup')
    config_exists = paths.config_path().exists()
    settings = WorkerSettings()
    # Pending edits accumulate here until final commit, so 'q' cancels cleanly.
    pending: dict[str, Any] = {}
    _show_paths(ui, config_exists, settings.is_complete)

    if not config_exists or not settings.is_complete:
        if config_exists:
            ui.warning('Existing configuration is incomplete. Required values follow.')
        _guided_initial_setup(ui, settings, pending)
    else:
        _update_menu(ui, settings, pending)

    ui.section('Review')
    _show_summary(ui, settings, pending)
    if not ui.confirm('Write this configuration', True):
        raise SystemExit('Setup cancelled.')

    if pending:
        settings.update(**pending)
    ui.success(f'Configuration written to {settings.config_path}')
    if settings.use_https and not is_ssl_configured():
        ui.note('HTTPS is enabled; a self-signed certificate will be generated')
        ui.note('on first ./swr start, or you can run ./swr cert create now.')
    ui.success('Setup complete.')
    ui.note('Start the service with: ./swr start')


def _show_paths(ui: TerminalUI, config_exists: bool, config_complete: bool) -> None:
    config_status = 'new'
    if config_exists:
        config_status = 'complete' if config_complete else 'incomplete'
    ui.section('Install Location')
    ui.table(
        [
            ('Data directory', str(paths.data_dir())),
            ('Config file', f'{paths.config_path()} ({config_status})'),
            ('Database', str(paths.database_path())),
            ('HTTPS certificates', _cert_status()),
        ]
    )


def _guided_initial_setup(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any]
) -> None:
    ui.section('New Configuration')
    ui.note('Press Enter to accept a value shown in brackets.')
    _configure_identity(ui, settings, pending, required=True)
    _configure_smtp(ui, settings, pending, required=True)
    _configure_service(ui, settings, pending, required=True)
    _configure_https(ui, settings, pending)
    _configure_access_passphrase(ui, settings, pending, default_set=True)


def _update_menu(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any]
) -> None:
    while True:
        _show_current_settings(ui, settings, pending)
        action = ui.choice(
            'Edit Menu',
            [
                ('1', 'Worker and manager identity'),
                ('2', 'SMTP delivery'),
                ('3', 'Service port'),
                ('4', 'Use HTTPS'),
                ('5', 'Access passphrase'),
                ('6', 'Review and save'),
                ('q', 'Quit without saving'),
            ],
            '6',
        )
        if action == '1':
            _configure_identity(ui, settings, pending, required=True)
        elif action == '2':
            _configure_smtp(ui, settings, pending, required=True)
        elif action == '3':
            _configure_service(ui, settings, pending, required=True)
        elif action == '4':
            _configure_https(ui, settings, pending)
        elif action == '5':
            _configure_access_passphrase(ui, settings, pending, default_set=False)
        elif action == '6':
            return
        elif action == 'q':
            raise SystemExit('Setup cancelled.')


def _show_current_settings(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any]
) -> None:
    ui.section('Current Configuration')
    _show_summary(ui, settings, pending)


# =============================================================================
# Section prompts — each one mutates `pending` only
# =============================================================================

def _configure_identity(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any], *, required: bool
) -> None:
    ui.section('Identity')
    ui.note('These names and addresses appear in generated reports.')
    pending['worker_name'] = ui.input(
        'Worker name',
        _effective(settings, pending, 'worker_name'),
        required=required,
    )
    pending['worker_email'] = ui.input(
        'Worker email',
        _effective(settings, pending, 'worker_email'),
        required=required,
        validator=_validate_email_like,
    )
    pending['manager_name'] = ui.input(
        'Manager name',
        _effective(settings, pending, 'manager_name'),
        required=required,
    )
    pending['manager_email'] = ui.input(
        'Manager email',
        _effective(settings, pending, 'manager_email'),
        required=required,
        validator=_validate_email_like,
    )


def _configure_smtp(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any], *, required: bool
) -> None:
    ui.section('SMTP Delivery')
    ui.note('The report is sent from the worker address to the manager address.')
    previous_security = _effective_smtp_security(settings, pending)
    pending['smtp_host'] = ui.input(
        'SMTP server address',
        _effective_smtp_host(settings, pending),
        required=required,
    )
    security_mode = _prompt_smtp_security_mode(ui, previous_security)
    pending['smtp_security'] = security_mode
    current_port = _effective_smtp_port(settings, pending)
    previous_default_port = str(previous_security.default_port)
    mode_default_port = str(security_mode.default_port)
    port_default = (
        mode_default_port
        if not current_port or current_port == previous_default_port
        else current_port
    )
    pending['smtp_port'] = int(
        ui.input(
            'SMTP port',
            port_default,
            required=True,
            validator=_validate_required_port,
        )
    )
    if security_mode.requires_auth:
        ui.note('TLS SMTP modes require authentication in this application.')
        existing_user = settings.smtp.username
        username = ui.input('SMTP username', existing_user, required=True)
        password_required = settings.smtp.credentials is None
        password_label = (
            'SMTP password'
            if password_required
            else 'SMTP password (blank keeps existing)'
        )
        while True:
            password = ui.password(password_label)
            if password or not password_required:
                break
            ui.error('SMTP password is required for TLS mail modes.')
        pending['smtp_username'] = username
        pending['smtp_password'] = password
        if not password:
            try:
                build_credentials(username, settings.smtp.password)
            except ValueError as exc:
                ui.error(f'Could not reuse stored credentials: {exc}')
                raise SystemExit(1) from exc
    else:
        ui.note('Plain SMTP is sent without authentication.')
        pending.pop('smtp_username', None)
        pending.pop('smtp_password', None)


def _configure_service(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any], *, required: bool
) -> None:
    ui.section('Service')
    current = pending.get('service_port', settings.service_port)
    pending['service_port'] = int(
        ui.input(
            'Service port',
            str(current or DEFAULT_SERVICE_PORT),
            required=required,
            validator=_validate_required_port,
        )
    )


def _configure_https(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any]
) -> None:
    ui.section('HTTPS')
    ui.note(
        'Enable HTTPS to run stand-alone with a self-signed certificate. '
        'Leave disabled when a reverse proxy (nginx, Caddy, etc.) handles '
        'public HTTPS in front of this app.'
    )
    ui.note(f'Current state: {_cert_status()}')
    default = bool(pending.get('use_https', settings.use_https))
    pending['use_https'] = ui.confirm('Use HTTPS', default)
    if pending['use_https'] and not is_ssl_configured():
        ui.note('A self-signed certificate will be generated on first start.')


def _configure_access_passphrase(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any], *, default_set: bool
) -> None:
    ui.section('Access Protection')
    passphrase_is_set = not settings.verify_passphrase('')
    status = 'enabled' if passphrase_is_set else 'not set'
    ui.note(f'Current passphrase status: {status}.')
    if passphrase_is_set:
        if not ui.confirm('Change or remove the access passphrase', False):
            return
        ui.note('Leave the new passphrase blank to remove access protection.')
    elif not ui.confirm('Set an access passphrase', default_set):
        pending['access_passphrase'] = ''
        ui.warning('Access protection is disabled. Login accepts an empty passphrase.')
        return

    first = ui.password('New access passphrase')
    if first:
        second = ui.password('Confirm access passphrase')
        if first != second:
            raise SystemExit('Passphrases did not match; setup cancelled.')
    pending['access_passphrase'] = first


# =============================================================================
# Summary rendering
# =============================================================================

def _show_summary(
    ui: TerminalUI, settings: WorkerSettings, pending: dict[str, Any]
) -> None:
    worker_name = _effective(settings, pending, 'worker_name')
    worker_email = _effective(settings, pending, 'worker_email')
    manager_name = _effective(settings, pending, 'manager_name')
    manager_email = _effective(settings, pending, 'manager_email')
    smtp_host = _effective_smtp_host(settings, pending)
    smtp_security = _effective_smtp_security(settings, pending)
    smtp_port = _effective_smtp_port(settings, pending)
    smtp_auth = smtp_security.requires_auth
    smtp_user = pending.get('smtp_username', settings.smtp.username)
    use_https = bool(pending.get('use_https', settings.use_https))

    if 'access_passphrase' in pending:
        access_status = 'enabled' if pending['access_passphrase'] else 'disabled'
    else:
        access_status = 'enabled' if not settings.verify_passphrase('') else 'disabled'

    rows = [
        ('Worker', _format_person(worker_name, worker_email)),
        ('Manager', _format_person(manager_name, manager_email)),
        ('SMTP server', smtp_host or '<unset>'),
        ('SMTP security', smtp_security.label),
        ('SMTP port', smtp_port or '(default)'),
        ('SMTP auth', 'required' if smtp_auth else 'disabled'),
        ('SMTP user', smtp_user if smtp_auth else '(none)'),
        ('Service port', pending.get('service_port', settings.service_port)),
        ('Use HTTPS', 'yes' if use_https else 'no'),
        ('Certificate state', _cert_status()),
        ('Access', access_status),
        ('Config path', str(settings.config_path)),
    ]
    ui.table(rows)


# =============================================================================
# Effective-value helpers (pending overrides current)
# =============================================================================

def _effective(settings: WorkerSettings, pending: dict[str, Any], key: str) -> str:
    return str(pending.get(key, getattr(settings, key, '')))


def _effective_smtp_host(settings: WorkerSettings, pending: dict[str, Any]) -> str:
    return str(pending.get('smtp_host', settings.smtp.host))


def _effective_smtp_security(
    settings: WorkerSettings, pending: dict[str, Any]
) -> SmtpSecurity:
    return pending.get('smtp_security', settings.smtp.security_mode)


def _effective_smtp_port(settings: WorkerSettings, pending: dict[str, Any]) -> str:
    if 'smtp_port' in pending:
        return str(pending['smtp_port'])
    return str(settings.smtp.port or '')


# =============================================================================
# Helpers
# =============================================================================

def _cert_status() -> str:
    cert = paths.cert_path()
    key = paths.key_path()
    if cert.exists() and key.exists():
        if is_ssl_configured():
            return 'cert.pem and key.pem present and valid'
        return 'cert.pem and key.pem present but INVALID (run ./swr cert regen)'
    if cert.exists() or key.exists():
        return 'incomplete certificate files present (run ./swr cert regen)'
    return 'no certificate files'


def _format_person(name: str, email: str) -> str:
    if name and email:
        return f'{name} <{email}>'
    if name:
        return name
    if email:
        return email
    return '<unset>'


def _prompt_smtp_security_mode(
    ui: TerminalUI, current: SmtpSecurity
) -> SmtpSecurity:
    default_choice = {
        SmtpSecurity.STARTTLS: '1',
        SmtpSecurity.SMTPS: '2',
        SmtpSecurity.NONE: '3',
    }.get(current, '1')
    choice = ui.choice(
        'SMTP Security Mode',
        [
            ('1', 'STARTTLS on port 587'),
            ('2', 'Implicit TLS / SMTPS on port 465'),
            ('3', 'None / plain SMTP on port 25'),
        ],
        default_choice,
    )
    return {
        '1': SmtpSecurity.STARTTLS,
        '2': SmtpSecurity.SMTPS,
        '3': SmtpSecurity.NONE,
    }[choice]


def _validate_email_like(value: str) -> str:
    value = value.strip()
    if '@' not in value or value.startswith('@') or value.endswith('@'):
        raise ValueError('Enter an email address.')
    return value


def _validate_required_port(value: str) -> str:
    value = value.strip()
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError('Enter a numeric port.') from exc
    if port < 1 or port > 65535:
        raise ValueError('Enter a port between 1 and 65535.')
    return str(port)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
