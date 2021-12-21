"""
Input using DeepSpeech.

See https://github.com/mozilla/DeepSpeech
"""

from   deepspeech         import Model
from   dexter.input       import Token
from   dexter.input.audio import AudioInput
from   dexter.core.log    import LOG

import numpy
import os
import pyaudio

# ------------------------------------------------------------------------------

# Typical installation location for deepspeech data
_MODEL_DIR = "/usr/local/share/deepspeech/models"

# ------------------------------------------------------------------------------

class DeepSpeechInput(AudioInput):
    """
    Input from DeepSpeech using the given language model.
    """
    def __init__(self,
                 notifier,
                 rate=None,
                 wav_dir=None,
                 model =os.path.join(_MODEL_DIR, 'models.pbmm'),
                 scorer=os.path.join(_MODEL_DIR, 'models.scorer')):
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
            The path to the DeepSpeech model file.
        :type  scorer:
        :param scorer:
            The path to the DeepSpeech scorer file.
        """
        # If these don't exist then DeepSpeech will segfault when inferring!
        if not os.path.exists(model):
            raise IOError("Not found: %s" % (model,))

        # Load in and configure the model.
        LOG.info("Loading model from %s" % (model,))
        self._model = Model(model)
        if os.path.exists(scorer):
            LOG.info("Loading scorer from %s" % (scorer,))
            self._model.enableExternalScorer(scorer)

        # Handle any rate override
        if rate is None:
            rate = self._model.sampleRate()

        # Wen can now init the superclass
        super(DeepSpeechInput, self).__init__(
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
