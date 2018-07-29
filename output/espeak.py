'''
Speech synthesis output using espeak.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import logging

from   dexter.core   import LOG
from   dexter.output import Output
from   espeak        import espeak

# ------------------------------------------------------------------------------

class EspeakOutput(Output):
    '''
    An output which logs as a particular level to the system's log.
    '''
    def __init__(self, rate=None, voice=None):
        '''
        @type  rate: int
        @param rate:
            The speed at which to speek. An integer value between 0 and 450. The
            default rate is 175.
        @type  voice: str
        @param voice:
            The voice to use. See C{espeak.list_voices()}.
        '''
        super(EspeakOutput, self).__init__()

        if rate is not None:
            espeak.set_parameter(espeak.Parameter.Rate, int(rate))
        if voice is not None:
            espeak.set_voice(str(voice))


    def write(self, text):
        '''
        @see Output.write
        '''
        # Simply pass it along to espeak
        espeak.synth(text)        
    

    def stop(self):
        '''
        @see Component.stop
        '''
        # Stop any pending speech
        espeak.cancel()


