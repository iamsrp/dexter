"""
Input using PocketSphinx.
"""

import os

from dexter.input              import Token
from dexter.input.audio        import AudioInput
from pocketsphinx.pocketsphinx import *

# ------------------------------------------------------------------------------

# Typical installation location for pocketsphinx data
_MODEL_DIR = "/usr/share/pocketsphinx/model"

class PocketSphinxInput(AudioInput):
    """
    Input from PocketSphinx using the US English language model.
    """
    def __init__(self,
                 state,
                 wav_dir=None):
        """
        @see AudioInput.__init__()
        """
        super(PocketSphinxInput, self).__init__(state,
                                                wav_dir=wav_dir)

        # Create a decoder with certain model.
        config = Decoder.default_config()
        config.set_string('-hmm',  os.path.join(_MODEL_DIR, 'en-us/en-us'))
        config.set_string('-lm',   os.path.join(_MODEL_DIR, 'en-us/en-us.lm.bin'))
        config.set_string('-dict', os.path.join(_MODEL_DIR, 'en-us/cmudict-en-us.dict'))
        self._decoder = Decoder(config)
        self._data    = b''


    def _feed_raw(self, data):
        """
        @see AudioInput._decode_raw()
        """
        # Just buffer it up
        self._data += data


    def _decode(self):
        """
        @see AudioInput._decode_raw()
        """
        # Decode the raw bytes
        try:
            self._decoder.start_utt()
            self._decoder.process_raw(self._data, False, True)
            self._decoder.end_utt()
        finally:
            self._data = b''

        tokens = []
        for seg in self._decoder.seg():
            word = seg.word
            prob = seg.prob
            vrbl = True

            # Start and end tokens
            if word == '<s>' or word == '</s>':
                continue

            # Non-verbal tokens
            if ('<' in word or
                '>' in word or
                '[' in word or
                ']' in word):
                vrbl = False

            # Strip any "(...)" appendage which details the path
            if '(' in word:
                word = word[:word.index('(')]

            # Save as a token in the result
            tokens.append(Token(word, prob, vrbl))

        # We're done!
        return tokens
