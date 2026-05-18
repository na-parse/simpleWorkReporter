'''Self-signed certificate helper.

In-process equivalent of:
    openssl req -x509 -newkey rsa:4096 -nodes \
        -out cert.pem -keyout key.pem -days 2920
'''

from __future__ import annotations

import datetime
from pathlib import Path
from ssl import PROTOCOL_TLS_SERVER, SSLContext

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from . import paths
from .defs import CERT_KEY_SIZE, CERT_ORG_NAME, CERT_ORG_UNIT, CERT_VALID_DAYS


# =============================================================================
# Public API
# =============================================================================

def create_self_signed_cert(hostname: str = 'localhost') -> bool:
    '''Create a self-signed cert/key pair at the configured paths.'''
    paths.data_dir().mkdir(parents=True, exist_ok=True)
    _write_ssl_files(paths.cert_path(), paths.key_path(), hostname)
    paths.key_path().chmod(0o600)
    paths.cert_path().chmod(0o644)
    return True


def validate_ssl_files(cert_path: Path, key_path: Path) -> bool:
    '''Return True if the cert/key files load as a usable TLS server pair.'''
    try:
        context = SSLContext(PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        return True
    except Exception:
        return False


def is_ssl_configured(
    cert_path: Path | None = None,
    key_path: Path | None = None,
) -> bool:
    '''Check that both files exist and form a valid TLS pair.'''
    cert_path = cert_path or paths.cert_path()
    key_path = key_path or paths.key_path()
    if cert_path.is_file() and key_path.is_file():
        return validate_ssl_files(cert_path, key_path)
    return False


def remove_ssl_files(
    cert_path: Path | None = None,
    key_path: Path | None = None,
) -> None:
    '''Remove existing SSL certificate files if present.'''
    cert_path = cert_path or paths.cert_path()
    key_path = key_path or paths.key_path()
    for file_path in (cert_path, key_path):
        if file_path.is_file():
            file_path.unlink()


# =============================================================================
# Internal helpers
# =============================================================================

def _write_ssl_files(cert_path: Path, key_path: Path, hostname: str) -> None:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=CERT_KEY_SIZE,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, CERT_ORG_NAME),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, CERT_ORG_UNIT),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=CERT_VALID_DAYS))
        .sign(private_key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
