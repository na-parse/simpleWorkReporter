'''
credparser / __main__.py

Enables direct module execution via `python -m credparser`

This file allows the credparser module to be executed as a package:
    python -m credparser

When Python encounters `python -m credparser`, it:
1. Locates the credparser package
2. Executes the __main__.py file within that package
3. Sets __package__ and __name__ appropriately
4. Provides a menu interface to access CLI functions

This differs from console_scripts entry points defined in pyproject.toml:
- Entry points (credparser-make, credparser-config) are only available after
  `pip install` and create actual CLI commands in the system PATH
- __main__.py works during development with `python -m credparser` and after
  installation with the same command

Relationship to pyproject.toml:
    [project.scripts]
    credparser-make = "credparser.make_cred:make_credentials_cli"
    credparser-config = "credparser.configure:configure_credparser_cli"

The CLI modules can also be invoked directly:
    python -m credparser.make_cred [OPTIONS]
    python -m credparser.configure [OPTIONS]

These entry points are separate from __main__.py. Both approaches serve
different use cases:
- Entry points: Direct CLI commands (credparser-make, credparser-config)
- Module execution: python -m credparser.make_cred, python -m credparser.configure
- __main__.py: Module execution with menu (python -m credparser)
'''
import sys
import logging

from .make_cred import make_credentials
from .configure import configure_credparser_cli

_logger = logging.getLogger(__name__)


def main():
    '''
    Menu-driven interface for credparser CLI operations.

    Allows users to select between credential generation and configuration
    without needing to remember specific command names.
    '''
    logging.basicConfig(level=logging.INFO)

    print()
    print('CredParser CLI')
    print('=' * 40)
    print()
    print('Select an operation:')
    print()
    print('  1  -  Generate credential string (credparser-make)')
    print('  2  -  Configure credparser settings (credparser-config)')
    print('  q  -  Quit')
    print()

    try:
        choice = input('Enter selection [1/2/q]: ').strip().lower()

        if choice == '1':
            _logger.debug('User selected: make_credentials')
            make_credentials()
        elif choice == '2':
            _logger.debug('User selected: configure_credparser_cli')
            configure_credparser_cli()
        elif choice == 'q':
            _logger.debug('User quit menu')
            print()
            sys.exit(0)
        else:
            print()
            print('Invalid selection. Please enter 1, 2, or q.')
            print()
            # Recursively call main for retry
            main()

    except KeyboardInterrupt:
        print()
        print()
        print('Operation cancelled.')
        sys.exit(0)
    except Exception as e:
        _logger.error(f'Unexpected error in main menu: {e}')
        print(f'Error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
