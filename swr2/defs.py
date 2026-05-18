'''Application-wide constants and default values.

Must remain dependency-free with respect to other swr2 modules.
'''

from __future__ import annotations

from pathlib import Path

# =============================================================================
# Application Identity
# =============================================================================

APP_NAME = 'simpleWorkReporter'
ENV_HOME = 'SWR_HOME'
LOG_NAMESPACE = 'swr2'


# =============================================================================
# Filesystem Defaults
# =============================================================================

DEFAULT_DIR_NAME = '.simpleWorkReporter'
CONFIG_FILENAME = 'worker.conf'
DATABASE_FILENAME = 'tasks.db'
SSL_CERT_FILENAME = 'cert.pem'
SSL_KEY_FILENAME = 'key.pem'

DEMO_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / 'fixtures' / 'demo_tasks.json'
)


# =============================================================================
# Web Service Defaults
# =============================================================================

DEFAULT_SERVICE_PORT = 5000

# 0.0.0.0 keeps the service LAN-reachable.
DEFAULT_BIND_HOST = '0.0.0.0'

AVAILABLE_THEMES = (
    'basic',
    'light-green',
    'solarized',
    'gruvbox-light',
    'catppuccin-latte',
    'github-light',
    'everforest-light',
    'ayu-light',
    'papercolor-light',
    'dark',
    'dark-blue',
    'solarized-dark',
    'nord',
    'tokyo-night',
    'github-dark',
    'one-dark',
    'ayu-dark',
    'papercolor-dark',
    'gruvbox',
    'dracula',
    'monokai',
    'catppuccin-mocha',
    'rose-pine',
    'everforest-dark',
    'kanagawa',
    'palenight',
    'cobalt2',
)

DEFAULT_THEME = 'basic'


# =============================================================================
# SMTP Delivery
# =============================================================================

# Default port per security mode; doubles as the canonical mode allow-list.
SMTP_SECURITY_DEFAULT_PORTS = {
    'starttls': 587,
    'smtps': 465,
    'none': 25,
}

SMTP_SECURITY_DEFAULT = 'starttls'

# Aliases accepted when normalizing user-supplied security mode strings.
SMTP_SECURITY_ALIASES = {
    '': 'starttls',
    'tls': 'starttls',
    'start_tls': 'starttls',
    'ssl': 'smtps',
    'implicit_tls': 'smtps',
    'implicit': 'smtps',
    'smtp_ssl': 'smtps',
    'plain': 'none',
    'no_tls': 'none',
    'none': 'none',
}

SMTP_SECURITY_LABELS = {
    'starttls': 'STARTTLS',
    'smtps': 'Implicit TLS / SMTPS',
    'none': 'None / plain SMTP',
}

SMTP_CONNECT_TIMEOUT = 30


# =============================================================================
# Mail Report Strings
# =============================================================================

EMAIL_SUBJECT_PREFIX = 'Work report:'
REPORT_NO_ENTRIES_LABEL = 'No entries'


# =============================================================================
# Task Database
# =============================================================================

TASK_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        description TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        sent INTEGER
    )
'''

# Single-row mutex enforced via the CHECK constraint. acquired_at is the
# epoch claim time (NULL when free); claims older than
# SEND_LOCK_STALE_SECONDS are taken over automatically so a crashed
# sender cannot lock the operation forever.
SEND_LOCK_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS send_lock (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        acquired_at INTEGER
    )
'''
SEND_LOCK_SEED_SQL = (
    'INSERT OR IGNORE INTO send_lock (id, acquired_at) VALUES (1, NULL)'
)
SEND_LOCK_STALE_SECONDS = 300

# Time-of-day applied to back-dated entries so same-date entries collapse to
# a single sortable instant.
DEFAULT_BACKDATED_TIME = (12, 0, 1)


# =============================================================================
# Access Control / Crypto
# =============================================================================

PBKDF2_PREFIX = 'pbkdf2_sha256'
PBKDF2_ITERATIONS = 260_000
SESSION_SECRET_BYTES = 32


# =============================================================================
# Self-Signed TLS Certificate
# =============================================================================

CERT_KEY_SIZE = 4096
CERT_VALID_DAYS = 2920
CERT_ORG_NAME = 'simpleWorkReporter'
CERT_ORG_UNIT = 'SelfSignForFlask'


# =============================================================================
# Logging
# =============================================================================

DEFAULT_LOG_LEVEL = 'INFO'
LOG_LEVEL_ENV_VAR = 'SWR_LOG_LEVEL'

LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Werkzeug already embeds its own timestamp, so we render only the message.
WERKZEUG_LOG_FORMAT = '%(message)s'


