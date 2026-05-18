'''
credparser / mutators

Manipulators for data encoding and decoding

'''
import logging
from .config import config
from .seed import MasterSeed
from .errors import *

import getpass
import hashlib
import base64
import secrets
from typing import Tuple
from pathlib import Path

_logger = logging.getLogger(__name__)


def binflip(invalue: int) -> int:
    ''' Reverse the bit order inside a byte '''
    return int('{:08b}'.format(invalue)[::-1], 2)

def nacl(length: int) -> str:
    ''' Salt generation / Using conf friendly characters '''
    grains = (
        "0123456789"
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    return ''.join(secrets.choice(grains) for _ in range(length))


def generate_key(master_seed: bytes, salt: str, signer: str) -> bytes:
    '''
    Generate a unique key using the master seed, salt, and signer.

    In general, we are expecting to use the OS level user as the 'signer'

    Key generation workflow:
      TRANSFORM: master seed is XORed with repeating salt/signer pattern
      HASH ROUNDS: salt determines a set number of hash rounds for key
    '''
    _logger.debug(f'Entered generate_key() with {signer=}')
    salt_bytes = str(salt).encode('ascii')
    signer_bytes = str(signer).encode('ascii')

    # Transform: XOR master_seed with repeated salt+username pattern
    pattern = (
        (salt_bytes + signer_bytes) *
        ((len(master_seed) // len(salt_bytes + signer_bytes)) + 1)
    )
    # Clip pattern to length of master_seed and XOR
    pattern = pattern[:len(master_seed)]
    transformed = bytes(a ^ b for a, b in zip(master_seed, pattern))

    # Determine hash rounds from salt
    salt_int = sum(ord(c) for c in salt)
    hash_rounds = (
        (salt_int % config.max_hash_rounds)
        if (salt_int % config.max_hash_rounds) > config.min_hash_rounds
        else config.min_hash_rounds
    )

    # Multiple hash rounds for additional transformation
    result = transformed
    for _ in range(hash_rounds):
        result = hashlib.sha512(result + salt_bytes + signer_bytes).digest()

    return result


def key_filter(data: bytes, key: bytes) -> bytes:
    ''' XOR the data against the key '''
    extended_key = (key * ((len(data) // len(key)) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, extended_key))


def _encode_credentials(
    username: str,
    password: str,
    signer: str = None,
    seed_path: Path = None
) -> str:
    '''
    Encode is wrapped to provide error handling and catching for data types
    '''
    _logger.debug('Encoding credentials')
    master_seed = MasterSeed(allow_init=True, seed_path=seed_path)

    if not isinstance(username, str) or not isinstance(password, str):
        raise InvalidDataType()

    # Catch all Exceptions during encode so we can provide a reliable
    #   exception for importers when this fails: EncodeFailure()
    try:
        result = encode(master_seed.seed, username, password, signer)
        _logger.debug('Credentials encoded successfully')
        return result
    except Exception as e:
        _logger.debug('Encode failed')
        errmsg = (
            f'Unexpected issue while encoding credentials: {e}'
        )
        raise EncodeFailure(errmsg) from None


def encode(
    master_seed: bytes,
    username: str,
    password: str,
    signer: str = None
) -> str:
    # Set signer to current OS username if not specified
    if signer is None:
        signer = getpass.getuser()

    salt = nacl(config.salt_len)
    _logger.debug(f'Generating key for encode with {signer=}')
    key = generate_key(master_seed, salt, signer)

    # Build message as bytes - username/password encoded to ASCII at boundary
    username_bytes = username.encode('ascii')
    password_bytes = password.encode('ascii')
    message = (
        salt.encode('ascii') +
        bytes([len(username_bytes)]) +
        username_bytes +
        password_bytes
    )

    # Apply binflip transformation on raw bytes
    egassem = bytes(binflip(b) for b in message)
    egassem_cipher = key_filter(egassem, key)

    cipher_b64 = base64.b64encode(egassem_cipher).decode('ascii')
    return salt + cipher_b64


def _decode_credentials(
    credential_string: str,
    signer: str = None,
    seed_path: Path = None,
) -> Tuple[str, str]:
    '''
    Actual decode method is wrapped to provide better error catching and
      handling for decryption failures.
    '''
    _logger.debug(f'Decoding credentials with {signer=}')

    master_seed = MasterSeed(allow_init=False, seed_path=seed_path)

    try:
        result = decode(master_seed.seed, credential_string, signer=signer)
        _logger.debug('Credentials decoded successfully')
        return result
    except DecodeFailure as e:
        _logger.debug('Decode failed')
        raise DecodeFailure(e) from None
    except Exception as e:
        _logger.debug('Decode failed')
        # Obscure package internals and ensure importers receive a
        # predictable exception when decode fails: DecodeFailure()
        errmsg = (
            f'Unable to decode the supplied credential string, '
            f'string, master_seed, or incorrect signer. \n--\n{e}'
        )
        raise DecodeFailure(errmsg)


def decode(
    master_seed: bytes,
    credential_string: str,
    signer: str = None
) -> Tuple[str, str]:
    # Extract plain-text Salt and base64 cipher text from credential string
    salt = credential_string[:config.salt_len]
    cipher_b64 = credential_string[config.salt_len:]
    cipher_text = base64.b64decode(cipher_b64)

    # Set signer to OS username if not set
    if signer is None:
        signer = getpass.getuser()
    _logger.debug(f'Generating key for decode with {signer=}')
    key = generate_key(master_seed, salt, signer)

    # Attempt to decrypt the cipher text
    egassem = key_filter(cipher_text, key)
    message = bytes(binflip(b) for b in egassem)

    # Data Extraction
    # - Extract raw bytes, then decode username/password to ASCII at boundary
    # - Decryption failures manifest during byte->str decode() as the raw
    #   byte codes will not align with real ASCII byte values
    try:
        # Extract and verify salt from message
        msg_salt_bytes = message[:config.salt_len]
        if salt.encode('ascii') != msg_salt_bytes:
            raise DecodeFailure('Invalid credential string, unable to decode')

        # Extract username length (single byte, supports 0-255)
        username_len = message[config.salt_len]

        # Extract username and password bytes, decode to ASCII at boundary
        username_start = config.salt_len + 1
        username_end = username_start + username_len
        username = message[username_start:username_end].decode('ascii')
        password = message[username_end:].decode('ascii')

    except UnicodeDecodeError:
        raise DecodeFailure('Invalid credential string, unable to decode')

    return username, password
