'''
Nathan's dev tools cause I suck
'''
import json
from pprint import pprint

def vardump(thisObj,indent=2):
    try:
        print(json.dumps(thisObj,indent=indent))
    except TypeError as e:
        if 'not JSON serializable' in e.args[0]:
            pprint(thisObj)
        else:
            raise
