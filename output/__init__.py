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
    def __init__(self, state):
        '''
        @type  state: L{State}
        @param state:
            The global State instance.
        '''
        super(Output, self).__init__(state)


    @property
    def is_output(self):
        '''
        Whether this component is an output.
        '''
        return True


    def write(self, text):
        '''
        Send the given text to the outside world.

        @type  text: str
        @param text:
            What to write.
        '''
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


class SpeechOutput(Output):
    '''
    An output which generates audio speech.

    When one of these classes has a state which is not C{IDLE} we deem it to be
    generating audio on the speaker.
    '''
    @property
    def is_speech(self):
        '''
        @see Component.is_speech()
        '''
        return True
    
