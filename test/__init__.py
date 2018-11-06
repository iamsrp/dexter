'''
Things to help with testing
'''

from dexter.core import Notifier

# ------------------------------------------------------------------------------

class _TestNofifier(Notifier):
    '''
    A notifier for use in doctests which does nothing.
    '''
    def update_status(self, component, status):
        pass

# ------------------------------------------------------------------------------

def tokenise(string):
    '''
    Turn a string into a list of tokens.
    '''
    from dexter.input import Token
    return [Token(e, 1.0, True) for e in string.split(' ')]

tokenize = tokenise

# ------------------------------------------------------------------------------

# Testing objects
NOTIFIER = _TestNofifier()
