'''
Speech synthesis output using festival.

@see http://www.cstr.ed.ac.uk/projects/festival/
'''

# For this you will need:
#  sudo apt install festival-dev festvox-rablpc16k
#  git clone https://github.com/iamsrp/festival.git
#  cd festival
#  sudo make install PYTHON=python3
#
# Other voices are available; see 'apt-cache search festvox'

from __future__ import (absolute_import, division, print_function, with_statement)

import festival
import time

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.output   import Output
from   threading       import Thread

# ------------------------------------------------------------------------------

# Trying to make the output run in a different thread from the main one results
# in this error:
#   SIOD ERROR: the currently assigned stack limit has been exceeded
# so we just let it run in the main thread instead. Kinda sucks but there you
# go.

# ------------------------------------------------------------------------------

class FestivalOutput(Output):
    '''
    An output which logs as a particular level to the system's log.
    '''
    def __init__(self, notifier, voice='voice_rab_diphone'):
        '''
        @see Output.__init__()
        @type  voice: str
        @param voice:
            The voice to use.
        '''
        super(FestivalOutput, self).__init__(notifier)

        festival.execCommand("(%s)" % str(voice))


    def write(self, text):
        '''
        @see Output.write
        '''
        if text is None:
            return

        text = str(text)
        try:
            self._notify(Notifier.WORKING)
            festival.sayText(text)

        except Exception as e:
            LOG.error("Failed to say '%s': %s" % (text, e))

        finally:
            self._notify(Notifier.IDLE)
