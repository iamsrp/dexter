"""
Input using DeepSpeech.
"""

from   deepspeech         import Model
from   dexter.input       import Token
from   dexter.input.audio import AudioInput
from   dexter.core.log    import LOG

import numpy
import os
import pyaudio

# ------------------------------------------------------------------------------

# In order to use this module you'll need to ensure that you have enough memory
# since its requirements are relatively huge. On a Raspberry Pi this means
# increasing your swap size to about 1G.
#
# So far I haven't been able to make the Pi work with the language model owing
# to memory constraints; even with 4G of swap.
#
# It's still _very_ slow on a Pi; well over a minute for a few seconds of audio.

# ------------------------------------------------------------------------------

# Typical installation location for deepspeech data
_MODEL_DIR = "/usr/local/share/deepspeech/models"

# ------------------------------------------------------------------------------

class DeepSpeechInput(AudioInput):
    """
    Input from DeepSpeech using the US English language model.
    """
    def __init__(self,
                 notifier,
                 wav_dir=None,
                 model =os.path.join(_MODEL_DIR, 'models.pbmm'),
                 scorer=os.path.join(_MODEL_DIR, 'models.scorer')):
        """
        @see AudioInput.__init__()

        :type  use_lm: bool
        :param use_lm:
            Whether to use the DeepSpeech language model for better predictions.
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

        # Wen can now init the superclass
        super(DeepSpeechInput, self).__init__(
            notifier,
            format=pyaudio.paInt16,
            channels=1,
            rate=self._model.sampleRate(),
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
