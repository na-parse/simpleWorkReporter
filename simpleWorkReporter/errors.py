'''
simpleWorkReporter - errors.py
---
Exception definitions and error handling for the app
'''

class DebugStop(Exception):
    ''' Debug Stop Point '''
    pass


class swrConfigError(Exception):
    ''' Configuration related issue '''
    pass

class swrDatabaseError(Exception):
    ''' Issues with the Database '''
    pass

class swrInternalError(Exception):
    ''' Internal processing error stub '''
    def __init__(self):
        self.message = f'Unexpected application state encountered.'
        self.state = f'error'
        super().__init__(self.message)
    
    def __str__(self):
        return self.message

class NotImplemented(Exception):
    ''' Stub to insert for functions that have not been implemented yet '''
    def __init__(self):
        self.message = f'Feature not implemented yet.'
        self.state = f'error'
        super().__init__(self.message)
    
    def __str__(self):
        return self.message
