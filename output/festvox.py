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

import re
import select
import subprocess
import time

# ------------------------------------------------------------------------------

class FestivalOutput(SpeechOutput):
    """
    A speech to text output using Festival in a subprocess.
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

        self._voice       = voice
        self._queue       = []
        self._subproc     = None
        self._interrupted = False


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
        self._interrupted = True

        if self._subproc is not None:
            # We do this by sending it a signal
            signal = subprocess.signal.SIGINT
            LOG.info("Sending %s to child process", signal)
            self._subproc.send_signal(signal)


    def _start(self):
        """
        @see Component._start()
        """
        # Start the subprocess here so that it can die directly (for whaterv
        # reason) rather than in the thread
        self._subproc = subprocess.Popen(('festival', '--interactive'),
                                         stdin =subprocess.PIPE,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL,
                                         universal_newlines=True)
        self._subproc.stdin.write("(%s)\n" % self._voice)
        self._subproc.stdin.flush()

        # Now spawn the worker thread
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

                # Ignore empty strings
                if not text:
                    LOG.info("Nothing to say...")
                    continue

                # We're about to say something, clear any interrupted flag ready
                # for any new one
                self._interrupted = False

                # I've got something to say (it's better to burn out, than to
                # fade away...)
                command = '(SayText "%s")\n' % text
                LOG.info("Sending: %s" % command.strip())
                self._notify(Notifier.WORKING)
                self._subproc.stdin.write(command)
                self._subproc.stdin.flush()

                # Wait for an approximate amount of time that we think it will
                # take to say what we were told to. Yes, this isn't great but we
                # don't have a good way to tell when festival has done talking
                # owing to the fact it buffers its output when it's piping.
                while (not self._interrupted and
                       time.time() - start < len(text) * 0.04):
                    time.sleep(0.1)

            except Exception as e:
                LOG.error("Failed to say '%s': %s" % (text, e))

            finally:
                self._notify(Notifier.IDLE)

        # Kill off the child
        try:
            if self._subproc is not None:
                self._subproc.terminate()
                self._subproc.communicate()
        except:
            pass


# ----------------------------------------------------------------------


class PyFestivalOutput(SpeechOutput):
    """
    A speech to text output which uses the pyfestival module.

    You might be able to pip install it, but I had to build it by hand using
    source from ``https://github.com/techiaith/pyfestival`` to make it work.

    Note that the current version holds on to the GIL. There's a fork in
    ``https://github.com/iamsrp/pyfestival`` which fixes this; a pull request
    has been made.
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
        super(PyFestivalOutput, self).__init__(state)

        self._voice         = voice
        self._queue         = []
        self._interrupted   = False
        self._boot_strapped = False
        self._start_error   = None


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
        self._interrupted = True


    def _start(self):
        """
        @see Component._start()
        """
        # Say that we're setting things up, since we might pause for a bit doing
        # it etc.
        self._notify(Notifier.INIT)

        # Now spawn the worker thread
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()

        # Wait for the thread to become properly active
        start = time.time()
        while not self._boot_strapped and thread.is_alive():
            if time.time() - start > 10:
                raise TimeoutError(
                    "Timed out waiting for worker thread to start"
                )
            time.sleep(0.1)

        # Back to idle when we're done either way
        self._notify(Notifier.IDLE)

        # What state is it in?
        if not thread.is_alive():
            raise ValueError(
                "Failed to start worker thread: %s: " %
                (self._start_error if self._start_error else "Unknown error")
            )


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
        # Festival is a little hokey and so we need to start it in the same
        # thread that we use it. Otherwise we get an message saying:
        #  SIOD ERROR: the currently assigned stack limit has been exceeded
        # As such we need to do everything here and communicate back success or
        # failure to the _start() method via member variables. Lovely.
        try:
            import festival
            festival.execCommand(self._voice)
            self._boot_strapped = True
        except Exception as e:
            self._start_error = e
            return

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

                # Ignore empty strings
                if not text:
                    LOG.info("Nothing to say...")
                    continue

                # We're about to say something, clear any interrupted flag ready
                # for any new one
                self._interrupted = False

                # We're talking so mark ourselves as active accordingly
                self._notify(Notifier.WORKING)

                # Break up the text into bits and say them so that we can
                # interrupt the output. Then say each part. We break on natural
                # pauses in the speech.
                for part in re.split(r'[\.,;:]', text):
                    if self._interrupted:
                        break
                    festival.sayText(part)

            except Exception as e:
                LOG.error("Failed to say '%s': %s" % (text, e))

            finally:
                self._notify(Notifier.IDLE)
