"""
Speech synthesis output using Mycroft's Mimic TTS models.

@see https://mycroft-ai.gitbook.io/docs/mycroft-technologies/mimic-tts/mimic-3
@see https://mycroftai.github.io/mimic3-voices/
"""

# Doing a pip install seems to work for Ubuntu:
#   pip install mycroft-mimic3-tts
#
# Installing on Raspberry Pi's 32bit OS is a little tricker though, since
# onnxruntime isn't available from pip. You can build it yourself by following
# the below onnxruntime instructions by just running the vanilla build.sh file,
# see here:
#   https://github.com/nknytk/built-onnxruntime-for-raspberrypi-linux/blob/master/BUILD.md
#
# The build might fail with an out-of-memory error on a Pi with less than 8Gb of
# memory so you might have to be creative with swap maybe?
#
# The clone operation seems to download half the internet, so it will take a
# while to do that, and then even longer to compile. And the 1.6.0 version in
# those instructions has a few compile errors but those are easy to fix:
#
#   pi@raspberrypi:~/onnxruntime/cmake/external/json/single_include/nlohmann $ git diff json.hpp
#   diff --git a/single_include/nlohmann/json.hpp b/single_include/nlohmann/json.hpp
#   index 6430930d..6fb5ef05 100644
#   --- a/single_include/nlohmann/json.hpp
#   +++ b/single_include/nlohmann/json.hpp
#   @@ -8491,7 +8491,7 @@ scan_number_done:
#            std::string result;
#            for (const auto c : token_string)
#            {
#   -            if ('\x00' <= c and c <= '\x1F')
#   +            if (c <= '\x1F')
#                {
#                    // escape control characters
#                    std::array<char, 9> cs{{}};
#   
#   pi@raspberrypi:~/onnxruntime/build/Linux/Release/pybind11/src/pybind11/include/pybind11/detail $ git diff internals.h
#   diff --git a/include/pybind11/detail/internals.h b/include/pybind11/detail/internals.h
#   index 067780c2..12c0f992 100644
#   --- a/include/pybind11/detail/internals.h
#   +++ b/include/pybind11/detail/internals.h
#   @@ -260,7 +260,8 @@ PYBIND11_NOINLINE inline internals &get_internals() {
#            auto *&internals_ptr = *internals_pp;
#            internals_ptr = new internals();
#    #if defined(WITH_THREAD)
#   -        PyEval_InitThreads();
#   +        Py_Initialize();
#            PyThreadState *tstate = PyThreadState_Get();
#            #if PY_VERSION_HEX >= 0x03070000
#                internals_ptr->tstate = PyThread_tss_alloc();

from   dexter.core           import Notifier, util
from   dexter.core.log       import LOG
from   dexter.output         import SpeechOutput
from   pathlib               import Path
from   tempfile              import NamedTemporaryFile
from   threading             import Thread

import time

# ------------------------------------------------------------------------------

class Mimic3Output(SpeechOutput):
    """
    A speech to text output using Mimic3.
    """
    def __init__(self,
                 state,
                 length_scale =1.0,
                 noise_scale  =0.66666,
                 noise_w      =0.8,
                 use_cuda     =False,
                 deterministic=True,
                 voices_dir   =None,
                 language     ="en_UK",
                 voice        =None,
                 speaker      =None):
        """
        @see Output.__init__()

        For info on the params please see the TTS source::
          https://github.com/MycroftAI/mimic3/blob/master/mimic3_tts/__main__.py
        That being said, unless you really want to dig through it all, you
        probably don't really care that much.

        :param length_scale:
            ``1.0`` is default speed, ``0.5`` is 2x faster.
        :param noise_scale:
            ``0`` to ``1``.
        :param noise_w:
            Variation in cadence (``[0-1]``).
        :param voices_dir:
            Directory with voices.
        :param use_cuda:
            Use Onnx CUDA execution provider (requires onnxruntime-gpu).
        :param deterministic:
            Ensure that the same audio is always synthesized from the same text.
        :param voice:
             Name of voice, expected in ``<voices-dir>``.
             E.g. ``en_UK/apope_low``.
        :param speaker:
            Name or number of speaker, if not the first.
        """
        super().__init__(state)

        # We will need pygame for this, but grab it lazily later
        self._pygame = None

        # We lazily import so that we may support different Mimic models as they
        # arise.
        from mimic3_tts import Mimic3Settings, Mimic3TextToSpeechSystem

        # Instaite it
        LOG.info("Creating Mimic3 instance")
        self._tts = Mimic3TextToSpeechSystem(
            Mimic3Settings(
                length_scale             =length_scale,
                noise_scale              =noise_scale,
                noise_w                  =noise_w,
                use_cuda                 =use_cuda,
                use_deterministic_compute=deterministic,
                voices_directories       =voices_dir,
                voice                    =voice,
                speaker                  =speaker,
            )
        )

        # State
        self._queue       = []
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


    def _start(self):
        """
        @see Component._start()
        """
        # Kick the engine to make it download anything which it needs to
        self._tts.begin_utterance()
        self._tts.speak_text("Initializing")
        tuple(self._tts.end_utterance())

        # And now start everything
        self._pygame = util.get_pygame()
        thread = Thread(name='Mimic3Output', target=self._run)
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
        from mimic3_tts import AudioResult

        # We make sure that we wait until the previous sentence has finished
        # before we start the next one.
        wait_until = 0

        # Keep going until we're told to stop.
        while self.is_running:
            if len(self._queue) == 0:
                time.sleep(0.1)
                continue

            # Else we have something to say
            try:
                start = time.time()
                text  = self._queue.pop()

                # Ignore empty strings
                if not text:
                    LOG.info("Nothing to say...")
                    continue

                # We're about to say something, clear any interrupted flag ready
                # for any new one
                self._interrupted = False

                # We're talking so mark ourselves as active accordingly
                self._notify(Notifier.WORKING)

                # Break this up into sentences so that we can handle
                # interruptions.
                for sentence in self._speechify(str(text)).split('. '):
                    # Turn the text into a wav
                    LOG.info("Saying '%s'", sentence)
                    self._tts.begin_utterance()
                    self._tts.speak_text(sentence)
                    for result in self._tts.end_utterance():
                        if isinstance(result, AudioResult):
                            # It seems simplest to write out the raw bytes to a
                            # file and then just read that back in, since that
                            # way it gets the right frequency etc. without
                            # having to mess with pygame's state. I know that
                            # this is terrible but...
                            for dirname in ('/dev/shm', '/tmp', '/var/tmp', '.'):
                                if Path(dirname).is_dir():
                                    with NamedTemporaryFile(dir=dirname,
                                                            suffix='.wav') as fh:
                                        # Write it out
                                        wav = result.to_wav_bytes()
                                        Path(fh.name).write_bytes(wav)

                                        # Read it back in and see how long it
                                        # will take to play. The play() call can
                                        # return early and we don't want to have
                                        # the sounds to overlap so we wait until
                                        # we think that the last one is done.
                                        sound = self._pygame.mixer.Sound(fh.name)
                                        while time.time() < wait_until:
                                            time.sleep(0.1)
                                        wait_until = time.time() + sound.get_length()
                                        sound.play()
                                    break

            except Exception as e:
                LOG.error("Failed to say '%s': %s" % (text, e))

            finally:
                # Go idle when we're done talking
                while time.time() < wait_until:
                    time.sleep(0.1)
                self._notify(Notifier.IDLE)
