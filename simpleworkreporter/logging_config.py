'''Application logging configuration.

werkzeug already embeds its own bracketed timestamp in the access-log
message body, so it gets its own formatter to avoid double dates.
'''

from __future__ import annotations

import logging
import os
import sys

from .defs import (
    DEFAULT_LOG_LEVEL,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    LOG_LEVEL_ENV_VAR,
    LOG_NAMESPACE,
    WERKZEUG_LOG_FORMAT,
)


_configured = False


def configure_logging() -> None:
    '''Install handlers for the simpleworkreporter and werkzeug loggers. Idempotent.'''
    global _configured
    level_name = os.environ.get(LOG_LEVEL_ENV_VAR, DEFAULT_LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)

    if _configured:
        logging.getLogger(LOG_NAMESPACE).setLevel(level)
        logging.getLogger('werkzeug').setLevel(level)
        return

    app_handler = logging.StreamHandler(sys.stdout)
    app_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    app_logger = logging.getLogger(LOG_NAMESPACE)
    app_logger.setLevel(level)
    app_logger.addHandler(app_handler)
    app_logger.propagate = False

    werkzeug_handler = logging.StreamHandler(sys.stdout)
    werkzeug_handler.setFormatter(logging.Formatter(WERKZEUG_LOG_FORMAT))
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(level)
    werkzeug_logger.handlers.clear()
    werkzeug_logger.addHandler(werkzeug_handler)
    werkzeug_logger.propagate = False

    _configured = True
