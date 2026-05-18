'''
credparser / __init__
'''
from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version('credparser')
except PackageNotFoundError:
    __version__ = 'embedded'

import logging
import os

# Configure debug logging if CREDPARSER_DEBUG is set
if os.environ.get('CREDPARSER_DEBUG'):
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        '%(name)s.%(funcName)s() [%(levelname)s] %(message)s'
    ))
    _pkg_logger = logging.getLogger(__name__)
    _pkg_logger.setLevel(logging.DEBUG)
    _pkg_logger.addHandler(_handler)

# Load and trigger configuration processing
from .config import config

# Expose credparser errors in base namespace
from .errors import *

# Main CredParser class object
from .credparser import CredParser

# Interactive credential creation guide
# Lazy import to avoid RuntimeWarning when running `python -m credparser.make_cred`
def make_credentials(*args, **kwargs):
    '''Guided interactive credential parser object creation (lazy wrapper)'''
    from .make_cred import make_credentials as _make_credentials
    return _make_credentials(*args, **kwargs)
