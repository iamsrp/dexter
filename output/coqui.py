"""
Speech synthesis output using Coqui's TTS model.

@see https://github.com/coqui-ai/TTS
"""

from   TTS.utils.manage      import ModelManager
from   TTS.utils.synthesizer import Synthesizer
from   dexter.core           import Notifier, util
from   dexter.core.log       import LOG
from   dexter.output         import SpeechOutput
from   pathlib               import Path
from   tempfile              import NamedTemporaryFile
from   threading             import Thread

import TTS
import time

# ------------------------------------------------------------------------------

class CoquiOutput(SpeechOutput):
    """
    A speech to text output using Coqui.

    For the params please see the TTS source. That being said, unless you really
    want to dig through it all, you probably don't really care that much. The
    main one which you will want to change will be ``model_name``; the list of
    models can be found in the ``.models.json`` file in the ``TTS`` top-level
    directory.
    """
    def __init__(self,
                 state,
                 models_path           =None,
                 model_name            ="tts_models/en/ljspeech/tacotron2-DCA",
                 vocoder_name          =None,
                 speakers_file_path    =None,
                 language_ids_file_path=None,
                 encoder_path          =None,
                 encoder_config_path   =None,
                 speaker_idx           =None,
                 language_idx          =None,
                 speaker_wav           =None,
                 use_cuda              =False):
        """
        @see Output.__init__()
        :type  model_name: str
        :param model_name:
            The model to use. See the list of models in the
            ``$TTS/.models.json`` file in the TTS tree in GitHub.
        """
        super(CoquiOutput, self).__init__(state)

        # We will need pygame for this, but grab it lazily later
        self._pygame = None

        # Get the model manager
        LOG.info("Creating Coqui Model Manager")
        manager = ModelManager(
                      Path(TTS.__file__).parent / ".models.json" if models_path is None
                      else models_path
                  )

        # Download everything which we need
        LOG.info("Downloading Coqui model")
        (model_path,
         config_path,
         model_item) = manager.download_model(model_name)

        LOG.info("Downloading Coqui vocoder")
        if not vocoder_name:
            vocoder_name = model_item["default_vocoder"]
        (vocoder_path,
         vocoder_config_path,
         vocoder_item)  = manager.download_model(vocoder_name)

        # Now we can create the synthesizer
        LOG.info("Creating Coqui synthesizer")
        self._synthesizer = Synthesizer(model_path,
                                        config_path,
                                        speakers_file_path,
                                        language_ids_file_path,
                                        vocoder_path,
                                        vocoder_config_path,
                                        encoder_path,
                                        encoder_config_path,
                                        use_cuda)

        # Needed when synthesizing
        self._speaker_idx  = speaker_idx
        self._language_idx = language_idx
        self._speaker_wav  = speaker_wav

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
        self._pygame = util.get_pygame()
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
                # interruptions
                for sentence in self._speechify(str(text)).split('. '):
                    # Turn the text into a wav
                    LOG.info("Saying '%s'", sentence)
                    wav = self._synthesizer.tts(sentence + '.',
                                                self._speaker_idx,
                                                self._language_idx,
                                                self._speaker_wav)

                    # Coqui gives us raw wav data and it's simplest to stuff it into
                    # a file and read it back in, so do that. Use temporary
                    # directories in order of desirability.
                    #
                    # At some point I'll figure out something better...
                    for dirname in ('/dev/shm', '/tmp', '/var/tmp', '.'):
                        if Path(dirname).is_dir():
                            with NamedTemporaryFile(dir=dirname, suffix='.wav') as fh:
                                fn = fh.name
                                self._synthesizer.save_wav(wav, fn)
                                self._pygame.mixer.Sound(fn).play()
                            break

            except Exception as e:
                LOG.error("Failed to say '%s': %s" % (text, e))

            finally:
                self._notify(Notifier.IDLE)
