'''
credparser / errors
'''

class credparserError(Exception):
    ''' Generic credparserError exception class '''
    pass

class CryptError(credparserError):
    ''' Cryptography related problems '''
    pass

class UsageError(credparserError):
    ''' Invalid credparser usage '''
    pass

class InitFailure(credparserError):
    ''' Initialization of credparser failed '''
    pass

class DecodeFailure(credparserError):
    ''' Credential string decoding failure '''
    pass

class EncodeFailure(credparserError):
    ''' Encoding failure -- serious and requires an issue '''
    pass

class ConfigError(credparserError):
    ''' Configuration load failure '''
    pass

class InvalidDataType(credparserError):
    ''' Username and Password must be ascii compatible str '''
    def __init__(self):
        super().__init__('Username and password values must be ascii compatible text')
