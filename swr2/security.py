'''Password hashing and secret helpers.'''

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from .defs import PBKDF2_ITERATIONS, PBKDF2_PREFIX, SESSION_SECRET_BYTES


def hash_passphrase(passphrase: str) -> str:
    '''Hash a passphrase for local access control.'''
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256', passphrase.encode('utf-8'), salt, PBKDF2_ITERATIONS
    )
    return ':'.join(
        [
            PBKDF2_PREFIX,
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode('ascii'),
            base64.b64encode(digest).decode('ascii'),
        ]
    )


def verify_passphrase(passphrase: str, stored_hash: str) -> bool:
    '''Return whether a passphrase matches a stored hash.'''
    if not stored_hash:
        return passphrase == ''
    try:
        prefix, iterations_text, salt_text, digest_text = stored_hash.split(':', 3)
        if prefix != PBKDF2_PREFIX:
            return False
        iterations = int(iterations_text)
        salt = base64.b64decode(salt_text.encode('ascii'))
        expected = base64.b64decode(digest_text.encode('ascii'))
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        'sha256', passphrase.encode('utf-8'), salt, iterations
    )
    return hmac.compare_digest(actual, expected)


def generate_session_secret() -> str:
    '''Return a fresh random Flask session secret as a base64 string.'''
    return base64.urlsafe_b64encode(os.urandom(SESSION_SECRET_BYTES)).decode('ascii')
