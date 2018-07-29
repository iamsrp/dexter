'''
How Dexter sends information to the outside world.

This might be via speech synthesis, a display, logging, etc.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from   dexter.core import Component

# ------------------------------------------------------------------------------

class Output(Component):
    '''
    A way to get information to the outside world.
    '''
    def __init__(self, notifier):
        '''
        @type  notifier: L{Notifier}
        @param notifier:
            The Notifier instance.
        '''
        super(Output, self).__init__(notifier)


    def write(self, text):
        '''
        Send the given text to the outside world.

        @type  text: str
        @param text:
            What to write.
        '''
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")
