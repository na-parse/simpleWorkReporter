'''
dependencies check and graceful missing module recommendations for anything
modules that are not part of a standard base python installation.
'''
errors = False
try:
    from flask import __file__ as _flask_file
except ModuleNotFoundError:
    errors = True
    print(
        f'MISSING: "flask" module failed to import, do you need to install it?\n'
        f' python3 -m pip install flask'
    )

if errors:
    print(f'\nResolve missing dependencies and then try running again.')
    exit(1)

valid = True
