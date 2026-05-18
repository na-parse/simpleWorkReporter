'''
credparser / make_cred.py

Interactive credential string generator.

Provides both a programmatic interface and CLI entry point for
generating encoded credential strings.

Usage:
    As a module:    python -m credparser.make_cred [--target NAME] [--signer NAME]
    As a command:   credparser-make [--target NAME] [--signer NAME]
    Programmatic:   from credparser import make_credentials
'''
import logging
import getpass
import sys
import argparse

from .credparser import CredParser

_logger = logging.getLogger(__name__)


def make_credentials(target: str = None, signer: str = None) -> CredParser:
    '''
    Guided interactive credential parser object creation

    Args:
        target (str, optional): Descriptive label for what the credentials are for
        signer (str, optional): Custom signer for cross-user/cross-platform
            credential sharing. Defaults to OS username via getpass.getuser().

    Returns a CredParser object with the credential field populated.
    '''
    _logger.debug('Starting make_credentials guide')
    print("Credential String Generator")
    print("=" * 40)
    print()
    print(
        f'Creating an encoded credential string using the credparser library.\n'
        f'For API keys: Use a descriptive label as username, API key as password.\n'
        f'\n'
    )

    try:
        if target is not None:
            print(f'Enter credentials for: {target}')

        if signer is not None:
            print(f'Using custom signer: {signer}')
            print()

        # Get username
        username = input("Username/Label: ").strip()
        if not username:
            print("Error: Username cannot be empty")
            sys.exit(1)

        # Get password securely
        password = getpass.getpass("Password/API Key: ")
        if not password:
            print("Error: Password cannot be empty")
            sys.exit(1)

        # Generate credential string
        _logger.debug('Creating CredParser object')
        creds = CredParser(
            username=username,
            password=password,
            signer=signer
        )

        print()
        print("Generated Credential String:")
        print("-" * 40)
        print(creds.credentials)
        print()

        # Verification
        print("Verification:")
        print(f"Username: {creds.username}")
        print(f"Password: {'*' * len(creds.password)}")
        if signer is not None:
            print(f"Signer:   {signer}")

        _logger.debug('make_credentials completed successfully')
        return creds

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(1)
    except Exception as e:
        _logger.debug(f'make_credentials failed: {e}')
        print(f"Error: {e}")
        sys.exit(1)


def make_credentials_cli() -> None:
    '''
    CLI wrapper for make_credentials with argument parsing.

    Handles command-line arguments and calls make_credentials accordingly.
    Entry point for credparser-make command.
    '''
    parser = argparse.ArgumentParser(
        prog='credparser-make',
        description='Generate encoded credential strings using credparser'
    )

    parser.add_argument(
        '--target',
        type=str,
        metavar='NAME',
        help='Descriptive label for the credential target'
    )

    parser.add_argument(
        '--signer',
        type=str,
        metavar='NAME',
        help='Custom signer for cross-user/cross-platform credential sharing '
             '(defaults to OS username)'
    )

    args = parser.parse_args()

    make_credentials(target=args.target, signer=args.signer)


if __name__ == '__main__':
    make_credentials_cli()
