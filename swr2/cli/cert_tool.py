'''Self-signed HTTPS certificate maintenance.'''

from __future__ import annotations

import argparse
import logging
import socket
import sys

from .. import paths
from ..certs import (
    create_self_signed_cert,
    is_ssl_configured,
    remove_ssl_files,
    validate_ssl_files,
)
from ..logging_config import configure_logging


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    '''Run certificate maintenance commands.'''
    configure_logging()
    parser = argparse.ArgumentParser(prog='cert_tool')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.add_parser('status', help='show current certificate state')
    subparsers.add_parser('create', help='create a self-signed pair (fails if files exist)')
    regen_parser = subparsers.add_parser(
        'regen', help='delete and recreate the self-signed pair'
    )
    regen_parser.add_argument(
        '-y', '--yes', action='store_true',
        help='confirm destructive regen without prompting',
    )
    delete_parser = subparsers.add_parser(
        'delete', help='remove certificate files'
    )
    delete_parser.add_argument(
        '-y', '--yes', action='store_true',
        help='confirm delete without prompting',
    )
    args = parser.parse_args(argv)
    if args.command in (None, 'status'):
        return _status()
    if args.command == 'create':
        return _create()
    if args.command == 'regen':
        return _regen(args.yes)
    if args.command == 'delete':
        return _delete(args.yes)
    return 2


def _status() -> int:
    cert = paths.cert_path()
    key = paths.key_path()
    print(f'cert: {cert} ({"present" if cert.exists() else "missing"})')
    print(f'key : {key} ({"present" if key.exists() else "missing"})')
    if cert.exists() and key.exists():
        valid = validate_ssl_files(cert, key)
        print(f'pair: {"valid" if valid else "INVALID"}')
        return 0 if valid else 1
    return 0


def _create() -> int:
    cert = paths.cert_path()
    key = paths.key_path()
    if cert.exists() or key.exists():
        print('Certificate or key file already exists; refusing to overwrite.', file=sys.stderr)
        print(f'  cert: {cert} ({"present" if cert.exists() else "missing"})', file=sys.stderr)
        print(f'  key : {key} ({"present" if key.exists() else "missing"})', file=sys.stderr)
        print('Run ./cert_tool regen to replace.', file=sys.stderr)
        return 1
    try:
        create_self_signed_cert(socket.gethostname())
    except Exception as exc:
        logger.error('certificate creation failed error=%s', exc)
        print(f'Failed to create certificate: {exc}', file=sys.stderr)
        return 1
    print(f'Created {cert}')
    print(f'Created {key}')
    return 0


def _regen(skip_confirm: bool) -> int:
    cert = paths.cert_path()
    key = paths.key_path()
    if (cert.exists() or key.exists()) and not skip_confirm and not _confirm(
        'Delete and recreate self-signed certificate'
    ):
        print('Cancelled.')
        return 1
    remove_ssl_files()
    try:
        create_self_signed_cert(socket.gethostname())
    except Exception as exc:
        logger.error('certificate regen failed error=%s', exc)
        print(f'Failed to regenerate certificate: {exc}', file=sys.stderr)
        return 1
    print(f'Recreated {cert}')
    print(f'Recreated {key}')
    if not is_ssl_configured():
        print('WARNING: new files do not validate as a TLS pair.', file=sys.stderr)
        return 1
    return 0


def _delete(skip_confirm: bool) -> int:
    cert = paths.cert_path()
    key = paths.key_path()
    if not (cert.exists() or key.exists()):
        print('No certificate files to delete.')
        return 0
    if not skip_confirm and not _confirm('Delete certificate files'):
        print('Cancelled.')
        return 1
    remove_ssl_files()
    print('Certificate files removed.')
    return 0


def _confirm(action: str) -> bool:
    try:
        response = input(f'{action}? Type "yes" to continue: ')
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return response.strip().lower() == 'yes'


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
