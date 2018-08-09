'''
Speech synthesis output using festival.

@see http://www.cstr.ed.ac.uk/projects/festival/
'''

# For this you will need:
#  sudo apt install festival festvox-rablpc16k
#
# Other voices are available; see 'apt-cache search festvox'

from __future__ import (absolute_import, division, print_function, with_statement)

import subprocess
import time

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.output   import Output
from   threading       import Thread

# ------------------------------------------------------------------------------

class FestivalOutput(Output):
    '''
    An output which logs as a particular level to the system's log.

    We run this in a subprocess since the in-process version tends to lock
    things up and also doesn't work outside the main thread.
    '''
    def __init__(self, notifier, voice='voice_rab_diphone'):
        '''
        @see Output.__init__()
        @type  voice: str
        @param voice:
            The voice to use.
        '''
        super(FestivalOutput, self).__init__(notifier)

        self._voice   = voice
        self._queue   = []
        self._subproc = None


    def write(self, text):
        '''
        @see Output.write
        '''
        if text is not None:
            self._queue.append(str(text))


    def _start(self):
        '''
        @see Component._start()
        '''
        # Start the subprocess here so that it can die directly (for whaterv
        # reason) rather than in the thread
        self._subproc = subprocess.Popen(('festival', '--pipe'),
                                         stdin=subprocess.PIPE,
                                         universal_newlines=True)
        self._subproc.stdin.write("(%s)\n" % self._voice)
        self._subproc.stdin.flush()

        # Now spawn the worker thread
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()


    def _stop(self):
        '''
        @see Component._stop()
        '''
        # Clear any pending dialogue
        self._queue = []


    def _run(self):
        '''
        The actual worker thread.
        '''
        # Keep going until we're told to stop
        while self.is_running:
            if len(self._queue) == 0:
                time.sleep(0.1)
                continue

            # Else we have something to say
            try:
                # Get the text, make sure that '"'s in it won't confuse things
                text = self._queue.pop()
                text = text.replace('"', '')
                self._notify(Notifier.WORKING)
                self._subproc.stdin.write('(SayText "%s")\n' % text)
                self._subproc.stdin.flush()

            except Exception as e:
                LOG.error("Failed to say '%s': %s" % (text, e))

            finally:
                self._notify(Notifier.IDLE)

        # Kill off the child
        try:
            self._subproc.terminate()
            self._subproc.communicate()
        except:
            pass
