'''
Input using audio data from the microphone.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import audioop
import math
import numpy
import os
import pyaudio
import time

from   collections  import deque
from   dexter.input import Input, Token
from   dexter.core  import LOG, Notifier
from   threading    import Thread

# ------------------------------------------------------------------------------

class AudioInput(Input):
    '''
    Base class for input from audio.

    Heavily adapted from::
      http://blog.justsophie.com/python-speech-to-text-with-pocketsphinx/
    '''
    def __init__(self,
                 pre_silence_limit=2.0,
                 mid_silence_limit=1.0,
                 prev_audio=1.5,
                 chunk=1024,
                 format=pyaudio.paInt16,
                 channels=1,
                 rate=16000):
        # Microphone stream config
        self._chunk    = chunk  # Chunks of bytes to read each time from mic
        self._format   = format
        self._channels = channels
        self._rate     = rate

        # Silence limits in seconds. The pre limit is the window where we look
        # for the start of speech. The mid limit is how long we keep recording
        # through silence, assuming that the speech is still going on.
        self._pre_silence_limit = pre_silence_limit
        self._mid_silence_limit = mid_silence_limit

        # Previous audio (in seconds) to prepend. When noise
        # is detected, how much of previously recorded audio is
        # prepended. This helps to prevent chopping the beginning
        # of the phrase.
        self._prev_audio = prev_audio

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
            thread = Thread(target=self._run)
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


    def _decode_raw(self, data):
        '''
        Decode the raw data.

        @rtype: tuple(L{Token})
        @return:
           The decoded tokens.
        '''
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


    def _run(self):
        '''
        Reads from the audio input stream and hands it off to be processed.
        '''
        # This possibly takes a while so tell the system what we're doing.
        self._notify(Notifier.INIT)

        # Ummm...
        rel = self._rate / self._chunk

        # How we keep track of the average sound level
        slide_size  = int(self._pre_silence_limit * rel)
        window_size = int(3 * slide_size)
        average_win = deque(maxlen=window_size)

        # How we detect if the noise level is high enough to warrant recording
        slid_win = deque(maxlen=slide_size)

        # Prepend audio from X seconds before noise was detected
        prev_audio = deque(maxlen=int(self._prev_audio * rel))

        # Start pulling in the audio stream
        p      = pyaudio.PyAudio()
        stream = p.open(format          =self._format,
                        channels        =self._channels,
                        rate            =self._rate,
                        input           =True,
                        frames_per_buffer=self._chunk)

        # Things which we'll use in the loop below
        audio         = None
        threshold     = None
        talking_start = 0

        # Keep listening until we are stopped
        while self._running:
            # Read in the next lump of data
            cur_data = stream.read(self._chunk)

            # Appending it to our sliding windows so that we may see if we have
            # silence or talking and can keep track of the averge.
            level = math.sqrt(abs(audioop.avg(cur_data, 4)))
            average_win.append(level)
            slid_win   .append(level)

            # Figure out the threshold given the last N seconds of audio,
            # leading up to our sample period.
            if len(average_win) == window_size:
                # If the threshold is None then we are entering this block for
                # the first time. That means we can tell the user that we're
                # active.
                if threshold is None:
                    LOG.info("Listening")
                    self._notify(Notifier.IDLE)

                # Get the averaging window, with the sliding window removed from
                # the end
                values = numpy.array(average_win)[:slide_size]

                # See what the top 20% of that looks like.
                count   = int((window_size - slide_size) * 0.2) + 1
                average = numpy.mean(sorted(values, reverse=True)[:count])

                # The threshold should be somwhere about this. The multiplier is
                # chosen by vague trial and error here.
                threshold = average * 2.5

                # Whether someone is likely talking.
                max_level = max(slid_win)
                talking = max_level > threshold
                LOG.debug("Max level and threshold are: %d %d",
                          max_level, threshold)

            else:
                # No-one is talking until we have enough data to compute the
                # average noise level.
                talking = False

            # If we think someone is talking then
            now = time.time()
            if talking:
                # Remember the last time that we heard someone talking
                talking_start = now

                # If we don't yet have any audio then we're starting the
                # recording
                if audio is None:
                    # Move the rolling window of recording to be the start of
                    # the audio
                    LOG.info("Starting recording")
                    self._notify(Notifier.ACTIVE)
                    audio = list(prev_audio)
                    prev_audio.clear()

                # Add on what we just recorded
                audio.append(cur_data)

            # We deem that talking is still happening if it started only a
            # little while ago
            elif ((now - talking_start) > self._mid_silence_limit and
                  audio is not None):
                # There's no talking but there us recorded audio. That means
                # someone just stopped talking.
                LOG.info("Finished recording")

                # Turn the audio data into text (hopefully!)
                self._notify(Notifier.WORKING)
                start = time.time()
                data = ''.join(audio)
                LOG.info("Decoding %0.2fs seconds of audio" %
                         (len(data) / 2 / self._rate))
                tokens = self._decode_raw(data)                
                LOG.info("Decoded audio in %0.2fs: %s" %
                         (time.time() - start, ([str(x) for x in tokens])))

                # Add then to the output
                self._output.append(tokens)

                # Reset to no audio and back to listening
                audio = None

                # Flush anything accumulated while we were parsing the phrase,
                # so that we don't fall behind
                available = stream.get_read_available()
                while (available > self._chunk):
                    LOG.debug("Junking backlog of %d", available)
                    stream.read(available)
                    available = stream.get_read_available()

                # And we're back to listening
                LOG.info("Listening")
                self._notify(Notifier.IDLE)

            else:
                # Update the rolling pre-talking buffer with what we just
                # recorderd.
                prev_audio.append(cur_data)

        # If we got here then _running was set to False and we're done
        LOG.info("Done listening")
        stream.close()
        p.terminate()