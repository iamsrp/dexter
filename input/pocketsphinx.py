'''
Input using PocketSphinx.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import os

from dexter.input              import Token
from dexter.input.audio        import AudioInput
from pocketsphinx.pocketsphinx import *

# ------------------------------------------------------------------------------

# Typical installation location for pocketsphinx data
_MODEL_DIR = "/usr/share/pocketsphinx/model"

class PocketSphinxInput(AudioInput):
    '''
    Input from PocketSphinx using the US English language model.
    '''
    def __init__(self,
                 notifier,
                 pre_silence_limit=2.0,
                 mid_silence_limit=1.0,
                 prev_audio=1.5):
        '''
        @see AudioInput.__init__()
        '''
        super(PocketSphinxInput, self).__init__(
            notifier,
            pre_silence_limit=pre_silence_limit,
            mid_silence_limit=mid_silence_limit,
            prev_audio=prev_audio
        )

        # Create a decoder with certain model.
        config = Decoder.default_config()
        config.set_string('-hmm',  os.path.join(_MODEL_DIR, 'en-us/en-us'))
        config.set_string('-lm',   os.path.join(_MODEL_DIR, 'en-us/en-us.lm.bin'))
        config.set_string('-dict', os.path.join(_MODEL_DIR, 'en-us/cmudict-en-us.dict'))
        self._decoder = Decoder(config)


    def _decode_raw(self, data):
        '''
        @see L{AudioInput._decode_raw()}
        '''
        # Decode the raw bytes
        self._decoder.start_utt()
        self._decoder.process_raw(data, False, True)
        self._decoder.end_utt()

        tokens = []
        for seg in self._decoder.seg():
            word = seg.word
            prob = seg.prob
            vrbl = True

            # Start and end tokens
            if word is '<s>' or word is '</s>':
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
