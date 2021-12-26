"""
Input using Vosk.

See https://alphacephei.com/vosk/

`pip3 install vosk` should be enough to install it on Raspberry Pi OS but you
will need the 64bit wheel from the install page for the 64bit Raspberry Pi OS.
You will need the 64bit OS if you want to run the full model, and 7Gb of memory
to instantiate it. (Adding swap works for this but is, of course, slow.)
"""

from   vosk               import Model, KaldiRecognizer, SetLogLevel
from   dexter.input       import Token
from   dexter.input.audio import AudioInput
from   dexter.core.log    import LOG

import json
import numpy
import os
import pyaudio

# ------------------------------------------------------------------------------

# A typical installation location for vosk data
_MODEL_DIR = "/usr/local/share/vosk/models"

# ------------------------------------------------------------------------------

class VoskInput(AudioInput):
    """
    Input from Vosk using the given language model.
    """
    def __init__(self,
                 notifier,
                 rate   =16000,
                 wav_dir=None,
                 model  =os.path.join(_MODEL_DIR, 'model')):
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
            The path to the Vosk model file.
        """
        # Load in and configure the model.
        if not os.path.exists(model):
            raise IOError("Not found: %s" % (model,))
        LOG.info("Loading model from %s, this could take a while", model)
        SetLogLevel(1 if LOG.getLogger().getEffectiveLevel() >= 20 else 2)
        self._model      = Model(model)
        self._recognizer = KaldiRecognizer(self._model, rate)
        LOG.info("Model loaded")

        # Wen can now init the superclass
        super(VoskInput, self).__init__(
            notifier,
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            wav_dir=wav_dir
        )

        # Where we put the results
        self._results = []


    def _feed_raw(self, data):
        """
        @see AudioInput._feed_raw()
        """
        # Attempt to decode it
        if self._recognizer.AcceptWaveform(data):
            self._add_result(self._recognizer.Result())


    def _decode(self):
        """
        @see AudioInput._decode()
        """
        # Collect anything remaining
        self._add_result(self._recognizer.FinalResult())

        # Ensure it's clear for next time
        self._recognizer.Reset()

        # Tokenize
        tokens = []
        LOG.debug("Decoding: %s" % self._results)
        for result in self._results:
            word = result.get('word',  '').strip()
            conf = result.get('conf', 0.0)
            if word and conf:
                tokens.append(Token(word, conf, True))

        # Done
        self._results = []

        # And give them all back
        LOG.debug("Got: %s" % ' '.join(str(i) for i in tokens))
        return tokens


    def _add_result(self, json_result):
        """
        Add in any result we have from the given JSON string.
        """
        result = json.loads(json_result)
        LOG.debug("Got %s" % json_result)

        # See what we got, if anything
        if 'result' in result:
            # A full result, which is the best
            self._results.extend(result['result'])
        elif 'text' in result:
            # A decoded text string
            for word in result['text'].split():
                if word:
                    self._results.append({ 'word' : word,
                                           'conf' :  1.0 })
