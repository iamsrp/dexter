"""
Input using the Coqui STT library.

See::
  https://github.com/coqui-ai/stt
  https://stt.readthedocs.io/en/latest/

You'll mainly just need to download the appropriate model and scorer
files. These can be found either by running the ``stt-model-manager`` or by
going to:
  https://coqui.ai/models
"""

from   stt                import Model
from   dexter.input       import Token
from   dexter.input.audio import AudioInput
from   dexter.core.log    import LOG

import numpy
import os
import pyaudio
import time

# ------------------------------------------------------------------------------

# A typical installation location for Coqui data
_MODEL_DIR = "/usr/local/share/coqui/models"

# ------------------------------------------------------------------------------

class CoquiInput(AudioInput):
    """
    Input from Coqui using the given language model.

    :param model:  The path to the model, typically called something like
                   ``model.tflite``.
    :param scorer: The path to the scorer, typically called something like
                   ``huge-vocabulary.scorer``.
    """
    def __init__(self,
                 notifier,
                 rate   =None,
                 wav_dir=None,
                 model  =os.path.join(_MODEL_DIR, 'model'),
                 scorer =os.path.join(_MODEL_DIR, 'scorer')):
        """
        @see AudioInput.__init__()

        :type  rate:
        :param rate:
            The override for the rate, if not the model's one.
        :type  wav_dir:
        :param wav_dir:
            Where to save the wave files, if anywhere.
        :type  model:
        :param model:
            The path to the Coqui model file.
        :type  scorer:
        :param scorer:
            The path to the Coqui scorer file.
        """
        # If these don't exist then Coqui will segfault when inferring!
        if not os.path.exists(model):
            raise IOError("Not found: %s" % (model,))

        # Load in and configure the model.
        start = time.time()
        LOG.info("Loading model from %s" % (model,))
        self._model = Model(model)
        if os.path.exists(scorer):
            LOG.info("Loading scorer from %s" % (scorer,))
            self._model.enableExternalScorer(scorer)
        LOG.info("Models loaded in %0.2fs" % (time.time() - start,))

        # Handle any rate override
        if rate is None:
            rate = self._model.sampleRate()

        # Wen can now init the superclass
        super(CoquiInput, self).__init__(
            notifier,
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            wav_dir=wav_dir
        )

        # Where we put the stream context
        self._context = None


    def _feed_raw(self, data):
        """
        @see AudioInput._feed_raw()
        """
        if self._context is None:
            self._context = self._model.createStream()
        audio = numpy.frombuffer(data, numpy.int16)
        self._context.feedAudioContent(audio)


    def _decode(self):
        """
        @see AudioInput._decode()
        """
        if self._context is None:
            # No context means no tokens
            LOG.warning("Had no stream context to close")
            tokens = []
        else:
            # Finish up by finishing the decoding
            words = self._context.finishStream()
            LOG.info("Got: %s" % (words,))
            self._context = None

            # And tokenize
            tokens = [Token(word.strip(), 1.0, True)
                      for word in words.split(' ')
                      if len(word.strip()) > 0]
        return tokens
