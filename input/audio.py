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
import wave

from   collections     import deque
from   dexter.input    import Input, Token
from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   threading       import Thread

# ------------------------------------------------------------------------------

class AudioInput(Input):
    '''
    Base class for input from audio.
    '''
    def __init__(self,
                 state,
                 chunk_size=128,
                 format=pyaudio.paInt16,
                 channels=1,
                 rate=16000,
                 wav_dir=None):
        '''
        @type  state: L{State}
        @param state:
            The State instance.
        @type  chunk_size: int
        @param chunk_size:
            The number of samples to read from the stream at once.
        @type  format: int
        @param format:
            The pyaudio format.
        @type  channels: int
        @param channels:
            The number of audio channels (typically 1).
        @type  rate: int
        @param rate:
            The sample rate. This is usually 16kHz for many speech to text
            systems.
        @type  wav_dir: str
        @param wav_dir:
            Where to save WAV files to, if we are doing so.
        '''
        super(AudioInput, self).__init__(state)

        # Microphone stream config
        self._chunk_size = chunk_size
        self._format     = format
        self._channels   = channels
        self._width      = pyaudio.get_sample_size(pyaudio.paInt16) * channels
        self._rate       = rate

        # Where to save the wav files, if anywhere. This should already exist.
        if wav_dir is not None and not os.path.isdir(wav_dir):
            raise IOError("Not a directory: %s" % wav_dir)
        self._wav_dir = wav_dir

        # What we receive
        self._output = list()


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


    def _start(self):
        '''
        @see Component._start()
        '''
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()


    def _save_bytes(self, data):
        """
        Save the raw bytes to a wav file.

        @type  data: str
        @param data:
            The bytes to save out.
        """
        if self._wav_dir is None:
            return

        filename = os.path.join(self._wav_dir, "%d.wav" % time.time())
        LOG.info("Saving data as %s" % filename)
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._width)
            wf.setframerate(self._rate)
            wf.writeframes(data)
            wf.close()


    def _decode_raw(self, data):
        '''
        Decode the raw data.

        @type  data: str
        @param data:
            The bytes to save decode.

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

        # The number of read calls which we expect per second. This corresponds
        # to many entries in a buffer constitute a second's worth of data.
        read_rate = self._rate / self._chunk_size

        # The buffer of historical audio data
        audio_buf = deque(maxlen=int(1.0 * read_rate))
        level_buf = deque(maxlen=int(3.0 * read_rate))

        # The index at which we cut the level buffer for the purposes of looking
        # for a change in the audio going from background to noisy, or vice
        # versa. This is what we are looking for when detecting speech.
        avg_idx = level_buf.maxlen // 3

        # Start pulling in the audio stream
        p      = pyaudio.PyAudio()
        stream = p.open(format           =self._format,
                        channels         =self._channels,
                        rate             =self._rate,
                        input            =True,
                        frames_per_buffer=self._chunk_size)

        # State etc.
        talking  = None  # True when we have detect talking
        speech   = None  # What we will process as speech data
        max_secs = 10

        # Keep listening until we are stopped
        while self.is_running:
            # We'll need this here and there below
            now = time.time()

            # Read in the next lump of data and get its average volume
            chunk = stream.read(self._chunk_size)
            level = math.sqrt(abs(audioop.avg(chunk, self._width)))

            # Accumulate into our buffers
            audio_buf.append(chunk)
            level_buf.append(level)

            # If we have not yet filled up the level buffer then we're done
            # here. Any analysis etc. will be inaccurate.
            if len(level_buf) != level_buf.maxlen:
                continue

            # Get the averaging window as a numpy array so that we can cut it
            # and so forth
            levels = numpy.array(level_buf)

            # Determine the background level of sound. We only do this if we
            # don't think that anyone is talking. If we are doing this for the
            # first time then we can note that we have become actively
            # listening.
            if talking is None:
                LOG.info("Listening")
                self._notify(Notifier.IDLE)
                talking       = False
                talking_start = 0

            # Only look to see if someone is speaking if the system is
            # not. Otherwise we will likely hear ourselves.
            if self._state.is_speaking() and talking:
                LOG.info("Ignoring talking since audio is being output")
                talking = False
                speech  = None

            # We are looking for the background levels. If we think that someone
            # is talking then the background sound going to be at the end of the
            # levels, else it will be at the start.
            ratio_up   = 2.0
            ratio_dn   = 1.1
            percentile = 0.75
            if not talking:
                # Looking for a step up in the latter part
                lo_levels = levels[        :avg_idx] # From start to avg_idx
                hi_levels = levels[-avg_idx:       ] # From avg_idx to end
                lo_pctl = numpy.sort(lo_levels)[int(len(lo_levels)* percentile)]
                hi_pctl = numpy.sort(hi_levels)[int(len(hi_levels)* percentile)]
                if lo_pctl * ratio_up < hi_pctl:
                    LOG.info("Detected start of speech "
                             "with levels going from %d to %d" %
                             (lo_pctl, hi_pctl))
                    talking = True
                    talking_start = now
            else:
                # Looking for a step down in the latter part
                lo_levels = levels[-avg_idx:       ] # From avg_idx to end
                hi_levels = levels[        :avg_idx] # From start to avg_idx
                lo_pctl = numpy.sort(lo_levels)[int(len(lo_levels)* percentile)]
                hi_pctl = numpy.sort(hi_levels)[int(len(hi_levels)* percentile)]
                LOG.info("Levels are hi=%d to lo=%d" % (hi_pctl, lo_pctl))
                if lo_pctl * ratio_dn < hi_pctl:
                    LOG.info("Detected end of speech "
                             "with levels going from %d to %d" %
                             (hi_pctl, lo_pctl))
                    talking = False

            # If the talking has been going on too long then just stop it. Quite
            # possibly the capture was fooled.
            if talking and now - talking_start > max_secs:
                LOG.info("Talking lasted over %ds; pushing to False" % max_secs)
                talking = False

            # Different behaviour depending on whether we think someone is
            # talking or not
            if talking:
                # If we don't yet have any audio then we're starting the
                # recording
                if speech is None:
                    # Move the rolling window of recording to be the start of
                    # the audio
                    LOG.info("Starting recording")
                    self._notify(Notifier.ACTIVE)
                    speech = list(audio_buf)

                # Add on what we just recorded
                speech.append(chunk)

            # We deem that talking is still happening if it started only a
            # little while ago
            elif speech is not None:
                # There's no talking but there is recorded audio. That means
                # someone just stopped talking.
                LOG.info("Finished recording")

                # Turn the audio data into text (hopefully!)
                self._notify(Notifier.WORKING)
                start = time.time()

                # Turn the stream into a list of bytes and junk the speech
                # buffer
                audio  = b''.join(speech)
                speech = None

                # Maybe save then as a wav file
                self._save_bytes(audio)

                # Now decode
                LOG.info("Decoding %0.2fs seconds of audio" %
                         (len(audio) / self._width / self._rate))
                tokens = self._decode_raw(audio)
                LOG.info("Decoded audio in %0.2fs: %s" %
                         (time.time() - start, ([str(x) for x in tokens])))

                # Add then to the output
                self._output.append(tokens)

                # Flush anything accumulated while we were parsing the phrase,
                # so that we don't fall behind
                available = stream.get_read_available()
                while (available > self._chunk_size):
                    LOG.debug("Junking backlog of %d", available)
                    stream.read(available)
                    available = stream.get_read_available()

                # And we're back to listening
                LOG.info("Listening")
                self._notify(Notifier.IDLE)

        # If we got here then _running was set to False and we're done
        LOG.info("Done listening")
        stream.close()
        p.terminate()
