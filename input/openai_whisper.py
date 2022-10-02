"""
Input using the OpenAI Whisper module..

See::
  https://github.com/openai/whisper

Since there is no PyTorch for the Pi this does not work on the Pi, at the time
of writing...
"""

from   dexter.input       import Token
from   dexter.input.audio import AudioInput
from   dexter.core.log    import LOG

import numpy
import os
import pyaudio
import time
import whisper

# ------------------------------------------------------------------------------

# The available models
_MODELS = ('tiny', 'base', 'small', 'medium', 'large')

# ------------------------------------------------------------------------------

class WhisperInput(AudioInput):
    """
    Input from Coqui using the given language model.
    """
    def __init__(self,
                 notifier,
                 rate     =16000,
                 model    ='base',
                 translate=True,
                 wav_dir  =None):
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
            The model type to use, one of 'tiny', 'base', 'small', 'medium',
            or 'large'.
        """
        # Wen can now init the superclass
        super().__init__(
            notifier,
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            wav_dir=wav_dir
        )

        # Set up the actual model and our params
        self._model = whisper.load_model(model)
        self._task = 'translate' if bool(translate) else 'transcribe'

        # Where we buffer to
        self._audio = None


    def _feed_raw(self, data):
        """
        @see AudioInput._feed_raw()
        """
        # Buffer it up. Whisper expects a numpy float32 array normalised to
        # +/-1.0 so we convert and divide by max-short.
        audio = numpy.frombuffer(data, numpy.int16  ) \
                     .astype    (      numpy.float32) / 2.0**15
        if self._audio is None:
            self._audio = audio
        else:
            self._audio = numpy.concatenate((self._audio, audio))


    def _decode(self):
        """
        @see AudioInput._decode()
        """
        if self._audio is None:
            return None

        # Turn the audio into speech
        try:
            result = self._model.transcribe(self._audio, task=self._task)
        finally:
            self._audio = None

        # Give it right back
        return [
            Token(word, 1.0, True) for word in result['text'].split()
        ]
