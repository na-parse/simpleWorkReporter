'''
dependencies check and graceful missing module recommendations for anything
modules that are not part of a standard base python installation.
'''
errors = ''
try:
    from flask import __file__ as _flask_file
except ModuleNotFoundError:
    errors += (
        f'MISSING: "flask" module failed to import, do you need to install it?\n'
        f' python3 -m pip install flask\n'
    )

try:
    from cryptography import __file__ as _cryptography_file
except ModuleNotFoundError:
    errors += (
        f'MISSING: "cryptography" module failed to import, do you need to install it?\n'
        f' python3 -m pip install cryptography\n'
    )

if errors:
    print(errors + '\n')
    print(f'Resolve missing dependencies and then try running again.')
    exit(1)

valid = True
