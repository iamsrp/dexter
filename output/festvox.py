"""
Speech synthesis output using festival.

For other voices are try something like `apt-cache search festvox`, depending on
your distribution.

@see http://www.cstr.ed.ac.uk/projects/festival/
"""

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.output   import SpeechOutput
from   threading       import Thread

import select
import subprocess
import time

# ------------------------------------------------------------------------------

class FestivalOutput(SpeechOutput):
    """
    An output which logs as a particular level to the system's log.

    We run this in a subprocess since the in-process version tends to lock
    things up and also doesn't work outside the main thread.
    """
    def __init__(self,
                 state,
                 voice='voice_cmu_us_slt_arctic_hts'):
        """
        @see Output.__init__()
        :type  voice: str
        :param voice:
            The voice to use.
        """
        super(FestivalOutput, self).__init__(state)

        self._voice   = voice
        self._queue   = []
        self._subproc = None


    def write(self, text):
        """
        @see Output.write
        """
        if text is not None:
            self._queue.append(str(text))


    def interrupt(self):
        """
        @see Output.interrupt
        """
        if self._subproc is not None:
            # We do this by sending it a signal
            signal = subprocess.signal.SIGINT
            LOG.info("Sending %s to child process", signal)
            self._subproc.send_signal(signal)


    def _readlines(self, blocking=True):
        """
        Do a read until something comes out on _subproc's stdout. By default we
        block until we have at least one line's worth of output.
        """
        result = ''
        while True:
            # Wait for something to be ready out the stdout file descriptor
            got = ''
            while (select.select([self._subproc.stdout], [], [], 0.1)[0] != []):
                got += self._subproc.stdout.read(1)
            LOG.debug("Got '%s'", got)

            # Did that yield anything?
            if len(got) == 0:
                # Got nothing, are we done?
                if not blocking or '\n' in result:
                    break
            else:
                # Append what we got
                result += got

        # Give back the result, broken up by newlines
        return result.split('\n')


    def _start(self):
        """
        @see Component._start()
        """
        # Start the subprocess here so that it can die directly (for whatever
        # reason) rather than in the thread
        self._subproc = subprocess.Popen(('festival', '--interactive'),
                                         bufsize=0,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         universal_newlines=True)

        # Configure it in a side-thread. Set the voice and make sure that the
        # output is synchronous so that it can be interrupted
        def config():
            for command in ("(%s)\n" % self._voice,
                            "(audio_mode 'sync)\n",
                            "(SayText \"\")\n"):
                LOG.info("Configuring with: %s", command.strip())
                self._subproc.stdin.write(command)
                self._subproc.stdin.flush()

            # Get back the results
            start = time.time()
            while time.time() < start + 1:
                result = self._readlines(blocking=False)
                if result and all(result):
                    LOG.info("Read configuration response: %s", result)
            LOG.info("Conguration complete")
        thread = Thread(target=config)
        thread.daemon = True
        thread.start()

        # Now spawn the worker thread to actually handle the output
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()


    def _stop(self):
        """
        @see Component._stop()
        """
        # Clear any pending dialogue
        self._queue = []


    def _run(self):
        """
        The actual worker thread.
        """
        # Keep going until we're told to stop
        while self.is_running:
            if len(self._queue) == 0:
                time.sleep(0.1)
                continue

            # Else we have something to say
            try:
                # Get the text, make sure that '"'s in it won't confuse things
                start = time.time()
                text  = self._queue.pop()
                text  = text.replace('"', '')

                # Ignore empty strings since they confuse Festival
                if not text:
                    LOG.info("Nothing to say...")
                    continue

                # I've got something to say (it's better to burn out, than to
                # fade away...)
                command = '(SayText "%s")\n' % text
                LOG.info("Sending: %s" % command.strip())
                self._notify(Notifier.WORKING)
                self._subproc.stdin.write(command)
                self._subproc.stdin.flush()

                # And read in the result, which should mean it's done
                for line in self._readlines():
                    LOG.info("Received: %s" % line)

            except Exception as e:
                LOG.error("Failed to say '%s': %s" % (text, e))

            finally:
                self._notify(Notifier.IDLE)

        # Kill off any child
        try:
            if self._subproc is not None:
                self._subproc.terminate()
                self._subproc.communicate()
        except:
            pass
