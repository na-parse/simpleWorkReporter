'''Start the web service from the command line.'''

from __future__ import annotations

import argparse
import logging
import socket
import sys

from .. import db
from .. import paths
from ..certs import create_self_signed_cert, is_ssl_configured
from ..defs import APP_NAME, DEFAULT_BIND_HOST
from ..logging_config import configure_logging
from ..settings import WorkerSettings
from ..web import create_app


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    '''Start the Flask service.'''
    parser = argparse.ArgumentParser(prog='start_server')
    parser.add_argument(
        '-b', '--bind',
        metavar='HOST',
        default=DEFAULT_BIND_HOST,
        help=(
            f'interface to bind to (default: {DEFAULT_BIND_HOST}); '
            'use 127.0.0.1 to restrict to loopback'
        ),
    )
    args = parser.parse_args(argv)
    bind_host = args.bind
    configure_logging()
    settings = WorkerSettings()
    if not paths.config_path().exists() or not settings.is_complete:
        logger.error('startup blocked; configuration is missing or incomplete')
        print(
            f'Configuration is required before starting {APP_NAME}.',
            file=sys.stderr,
        )
        print('Run ./setup_server first.', file=sys.stderr)
        print(f'Expected config path: {paths.config_path()}', file=sys.stderr)
        return 1
    try:
        app = create_app(settings)
    except db.DatabaseError as exc:
        logger.error('startup blocked; database unusable error=%s', exc)
        print(f'Database error: {exc}', file=sys.stderr)
        print('Run ./db_tool init to repair, or correct the data directory.', file=sys.stderr)
        return 1
    ssl_context = _prepare_ssl(settings)
    if ssl_context is False:
        return 1
    mode = 'https' if ssl_context else 'http'
    logger.info(
        'starting web service mode=%s host=%s port=%s',
        mode, bind_host, settings.service_port,
    )
    if ssl_context:
        print(f'Starting {APP_NAME} in HTTPS mode on {bind_host}:{settings.service_port}.')
        print('Browser URLs must use https://.')
    else:
        print(f'Starting {APP_NAME} in HTTP mode on {bind_host}:{settings.service_port}.')
        print('Use this behind a reverse proxy if public HTTPS is required.')
    app.run(host=bind_host, port=settings.service_port, ssl_context=ssl_context)
    return 0


def _prepare_ssl(settings: WorkerSettings):
    '''Return an ssl_context tuple, None for HTTP, or False on fatal error.

    Behavior driven by `settings.use_https`:
      - off: returns None; cert files (if any) are ignored.
      - on + valid cert pair: returns (cert_path, key_path) tuple.
      - on + no cert files: auto-generates a self-signed pair, then returns it.
      - on + files exist but invalid: prints actionable error, returns False.
    '''
    if not settings.use_https:
        return None
    cert = paths.cert_path()
    key = paths.key_path()
    any_present = cert.exists() or key.exists()
    if not any_present:
        logger.info('use_https=on with no cert files; auto-generating self-signed pair')
        print('use_https is enabled; generating self-signed certificate...')
        try:
            create_self_signed_cert(socket.gethostname())
        except Exception as exc:
            logger.error('certificate generation failed error=%s', exc)
            print(f'Failed to generate self-signed certificate: {exc}', file=sys.stderr)
            return False
        print(f'  cert: {cert}')
        print(f'  key : {key}')
    if not is_ssl_configured():
        logger.error('startup blocked; use_https=on but cert files are missing or invalid')
        print('use_https is enabled but the certificate files are missing or invalid:', file=sys.stderr)
        print(f'  cert: {cert} ({"present" if cert.exists() else "missing"})', file=sys.stderr)
        print(f'  key : {key} ({"present" if key.exists() else "missing"})', file=sys.stderr)
        print('Run ./cert_tool regen to replace them, or ./cert_tool delete + ', file=sys.stderr)
        print('./setup_server to disable HTTPS.', file=sys.stderr)
        return False
    return (str(cert), str(key))


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
