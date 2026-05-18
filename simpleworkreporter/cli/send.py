'''Send pending reports from the command line.'''

from __future__ import annotations

import argparse
import logging
import sys

from ..logging_config import configure_logging
from ..mail import MailSendError, ReportFlagError, send_pending_report
from ..settings import WorkerSettings


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    '''Send the current pending report.'''
    parser = argparse.ArgumentParser(
        prog='swr send',
        description=(
            'Send the current pending report headlessly. Normal output goes '
            'to stdout, errors go to stderr; cron operators can redirect '
            'stdout to /dev/null and still receive errors via MAILTO.'
        ),
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help=(
            'Force-acquire the send lock even if another claim is fresh. '
            'Use when a previous send is known-stuck; otherwise wait it out.'
        ),
    )
    args = parser.parse_args(argv)
    configure_logging()
    if args.force:
        logger.warning('swr send --force: bypassing send_lock freshness check')
    try:
        count = send_pending_report(WorkerSettings(), force=args.force)
    except MailSendError as exc:
        logger.error('headless report send failed error=%s', exc)
        print(str(exc), file=sys.stderr)
        return 1
    except ReportFlagError as exc:
        # Distinct exit code: email was delivered but DB flagging failed.
        # Operator must intervene before next send to avoid a duplicate.
        print(str(exc), file=sys.stderr)
        return 2
    logger.info('headless report send completed entries=%s', count)
    if count:
        print(f'Sent report with {count} entries.')
    else:
        print('No unsent entries.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
