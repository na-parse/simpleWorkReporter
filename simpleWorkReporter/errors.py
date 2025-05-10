'''
simpleWorkReporter - errors.py
---
Exception definitions and error handling for the app
'''

class swrConfigError(Exception):
    ''' Configuration related issue '''
    pass

class swrInternalError(Exception):
    ''' Internal processing error stub '''
    def __init__(self):
        self.message = f'Unexpected application state encountered.'
        self.state = f'error'
        super().__init__(self.message)
    
    def __str__(self):
        return self.message

