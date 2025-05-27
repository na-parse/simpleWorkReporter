'''
simpleWorkReporter - sslcert.py
    Provides a basic method for creating self-signed certificates for running
    the web server with SSL and managing, validating the cert files.

    This produces an x509 certificate equivalent to the openssl command:
        openssl req -x509 -newkey rsa:4096 -nodes \
            -out cert.pem -keyout key.pem \
            -days 2920
'''
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime
import os
from pathlib import Path
from ssl import SSLContext, PROTOCOL_TLS_SERVER


def create_ssl_files(cert_path: Path, key_path: Path):
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"simpleWorkReporter"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"SelfSignForFlask"),
    ])

    cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=2920)
        ).sign(private_key, hashes.SHA256())

    # Write files
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))


def validate_ssl_files(cert_path: Path, key_path: Path) -> bool:
    '''
    Read the cert and key files to make sure they are good
    Returns True for valid, False if there is a problem.
    '''
    try:
        context = SSLContext(PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        return True
    except Exception as e:
        return False


def is_ssl_configured(cert_path: Path, key_path: Path) -> bool:
    """Check if SSL certificates are properly configured."""
    if (
        os.path.isfile(cert_path)
        and os.path.isfile(key_path)
    ):
        return validate_ssl_files(cert_path, key_path)
    return False


def remove_ssl_files(cert_path: Path, key_path: Path):
    """Remove existing SSL certificate files."""
    if os.path.isfile(cert_path):
        os.remove(cert_path)
    if os.path.isfile(key_path):
        os.remove(key_path)