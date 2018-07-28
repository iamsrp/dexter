'''
Input using PocketSphinx
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import audioop
import math
import os
import pyaudio
import time

from collections               import deque
from dexter.input              import Input, Token
from dexter.core               import LOG
from pocketsphinx.pocketsphinx import Decocder
from threading                 import Thread
#from sphinxbase.sphinxbase     import *

# ------------------------------------------------------------------------------

# Typical installation location for pocketsphinx data
_MODEL_DIR = "/usr/share/pocketsphinx/model"

class PocketSphinxInput(Input):
    '''
    Input from PocketSphinx.

    Adapted from::
      http://blog.justsophie.com/python-speech-to-text-with-pocketsphinx/
    '''
    def __init__(self, silence_limit=1.0, prev_audio=0.5):
        # Microphone stream config
        self._chunk    = 1024  # Chunks of bytes to read each time from mic
        self._format   = pyaudio.paInt16
        self._channels = 1
        self._rate     = 16000

        # Silence limit in seconds. The max ammount of seconds where
        # only silence is recorded. When this time passes the
        # recording finishes and the file is decoded
        self._silence_limit = silence_limit

        # Previous audio (in seconds) to prepend. When noise
        # is detected, how much of previously recorded audio is
        # prepended. This helps to prevent chopping the beginning
        # of the phrase.
        self._prev_audio = prev_audio

        # The threshold of sound level at which we start recording. Computed
        # dynamically when the system is started.
        self._threshold = None

        # Create a decoder with certain model.
        config = Decoder.default_config()
        config.set_string('-hmm',  os.path.join(_MODEL_DIR, 'en-us/en-us'))
        config.set_string('-lm',   os.path.join(_MODEL_DIR, 'en-us/en-us.lm.bin'))
        config.set_string('-dict', os.path.join(_MODEL_DIR, 'en-us/cmudict-en-us.dict'))

        # Creaders decoder object for streaming data
        self._decoder = Decoder(config)

        # Whether we are running or not
        self._running = False

        # What we receive
        self._output = list()


    def start(self):
        '''
        @see Component.start
        '''
        if not self._running:
            self._running = True
            thread = Thread(run=self._run)
            thread.daemon = True
            thread.start()


    def stop(self):
        '''
        @see Component.stop
        '''
        self._running = False


    def read(self):
        '''
        @see Input.read
        '''
        if len(self._output) > 0:
            try:
                return self._output.pop()
            except:
                pass
        return None


    def _init_mic(self, num_samples=50):
        '''
        Gets average audio intensity of your mic sound. You can use it to get
        average intensities while you're talking and/or silent. The average is
        the avg of the .2 of the largest intensities recorded.
        '''
        LOG.info("Getting intensity values from microphone")
        p = pyaudio.PyAudio()
        stream = p.open(format          =self._format,
                        channels        =self._channels,
                        rate            =self._rate,
                        input           =True,
                        frames_per_buffer=self._chunk)

        values = [math.sqrt(abs(audioop.avg(stream.read(self._chunk), 4)))
                  for x in range(num_samples)]
        values = sorted(values, reverse=True)
        r = sum(values[:int(num_samples * 0.2)]) // int(num_samples * 0.2)
        LOG.info("Average audio intensity is ", r)

        # Set the threshold to just above the limit
        self._threshold = int(max(r, 500) * 1.5)

        # And give back the audio
        return (p, stream)


    def _decode_raw(self, data):
        # Decode the raw bytes
        LOG.info("Decoding phrase")
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
            if '<' in word or '>' in word:
                vrbl = False

            # Strip any "(...)" appendage
            if '(' in word:
                word = word[:word.index('(')]

            tokens.append(Token(word, prob, vrbl))

        LOG.info("Decoded: %s" % (tokens,))

        return tokens


    def _run(self):
        '''
        Reads from the audio input stream, extracts phrases from it and calls
        pocketsphinx to decode the sound.
        '''
        # Ummm...
        rel = self._rate / self._chunk

        # How we detect if the noise level is high enough to warrant recording
        slid_win = deque(maxlen=int(self._silence_limit * rel))

        # Prepend audio from X seconds before noise was detected
        prev_audio = deque(maxlen=int(self._prev_audio * rel))

        # Calibrate the audio and get our handle on it
        (p, stream) = self._init_mic()
        LOG.info("Mic set up and listening")

        # Keep listening until we are stopped
        audio = None
        while self._running:
            # Read in the next lump of data
            cur_data = stream.read(self._chunk)

            # Appending it to our sliding window so that we may see if we have
            # silence or talking.
            slid_win.append(math.sqrt(abs(audioop.avg(cur_data, 4))))

            # Whether someone is likely talking.
            talking = sum([x > self._threshold for x in slid_win]) > 0

            # If we think someone is talking then
            if talking:
                # If we don't yet have any audio then we're starting the
                # recording
                if audio is None:
                    LOG.info("Starting recording of phrase")
                    # Move the rolling window of recording to be the start of
                    # the audio
                    audio = list(prev_audio)
                    prev_audio.clear()

                # Add on what we just recorded
                audio.append(cur_data)

            elif audio is not None:
                # There's no talking but there us recorded audio. That means
                # someone just stopped talking.
                LOG.info("Finished recording")

                # Queue it for handling
                self._output.append(self._decode_raw(''.join(audio)))

                # Reset to no audio and back to listening
                audio = None

                # And we're back to listening
                LOG.info("Listening ...")

            else:
                # Update the rolling pre-talking buffer with what we just
                # recorderd.
                prev_audio.append(cur_data)

        # If we got here then _running was set to False and we're done
        LOG.info("Done listening")
        stream.close()
        p.terminate()
