'''
Speech synthesis output using espeak.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import time

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.output   import Output
from   espeak          import espeak
from   threading       import Thread

# ------------------------------------------------------------------------------

class EspeakOutput(Output):
    '''
    An output which logs as a particular level to the system's log.
    '''
    def __init__(self, notifier, rate=None, voice=None):
        '''
        @see Output.__init__()
        @type  rate: int
        @param rate:
            The speed at which to speek. An integer value between 0 and 450. The
            default rate is 175.
        @type  voice: str
        @param voice:
            The voice to use. See C{espeak.list_voices()}.
        '''
        super(EspeakOutput, self).__init__(notifier)

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


    def _start(self):
        '''
        @see Component._start()
        '''
        thread = Thread(target=self._do_notify)
        thread.daemon = True
        thread.start()


    def _stop(self):
        '''
        @see Component._stop()
        '''
        # Stop any pending speech
        espeak.cancel()


    def _do_notify(self):
        '''
        Handle sending notifications to denote espeak's state.
        '''
        state = Notifier.IDLE
        while self.is_running:
            # If espeak is playing then we are working then so are we, else
            # we're not
            if espeak.is_playing():
                new_state = Notifier.WORKING
            else:
                new_state = Notifier.IDLE

            # Update the state if it has changed
            if new_state != state:
                state = new_state
                self._notify(state)

            # Don't busy-wait
            time.sleep(0.1)
