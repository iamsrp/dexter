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

    Heavily adapted from::
      http://blog.justsophie.com/python-speech-to-text-with-pocketsphinx/
    which looks to have partly come from Example 22 in:
      https://www.programcreek.com/python/example/100708/audioop.avg
    '''
    def __init__(self,
                 state,
                 pre_silence_limit=1.0,
                 mid_silence_limit=0.1,
                 prev_audio=1.5,
                 max_audio=10.0,
                 chunk=128,
                 format=pyaudio.paInt16,
                 channels=1,
                 rate=16000,
                 wav_dir=None):
        '''
        @type  state: L{State}
        @param state:
            The State instance.
        @type  pre_silence_limit: float
        @param pre_silence_limit:
            Number of seconds to look for sound in before a command.
        @type  mid_silence_limit: float
        @param mid_silence_limit:
            Number of seconds in a command before we consider it done.
        @type  prev_audio: float
        @param prev_audio:
            Number of seconds of leading audio to use before we started 
            recording.
        @type  chunk: int
        @param chunk:
            The number of things to read from the stream at once.
        @type  format: int
        @param format:
            The pyaudio format.
        @type  channels: int
        @param channels:
            The number of audio channels (typically 1).
        @type  rate: int
        @param rate:
            The sample rate. This is usually 16,000 for many speech to text
            systems.
        @type  wav_dir: str
        @param wav_dir:
            Where to save WAV files to, if we are doing so.
        '''
        super(AudioInput, self).__init__(state)

        # Microphone stream config
        self._chunk    = chunk  # Chunks of bytes to read each time from mic
        self._format   = format
        self._width    = pyaudio.get_sample_size(pyaudio.paInt16)
        self._channels = channels
        self._rate     = rate

        # Where to save the wav files, if anywhere. This should already exist.
        if wav_dir is not None and not os.path.isdir(wav_dir):
            raise IOError("Not a directory: %s" % wav_dir)
        self._wav_dir = wav_dir

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

        # The maximum about of audio which we'll record.
        self._max_audio = max_audio

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

        # Ummm...
        rel = self._rate / self._chunk

        # How we keep track of the average sound level
        slide_size  = int(self._pre_silence_limit * rel)
        window_size = int(2 * slide_size)
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

        # Threshold multipliers for detecting the start of talking and the
        # end. This is what we multiply the roling average sound levels by.
        threshold_over  = 1.75
        threshold_under = 1.25

        # Things which we'll use in the loop below
        audio              = None
        threshold          = None
        log_threshold      = 0
        log_threshold_time = 0
        talking            = False
        talking_start      = 0
        talking_last       = 0

        # Keep listening until we are stopped
        while self.is_running:
            # We'll need this here and there below
            now = time.time()

            # Read in the next lump of data
            cur_data = stream.read(self._chunk)

            # Determine the average level of this chunk and append it to the
            # sliding window which we use to detect elevated volumes.
            level = math.sqrt(abs(audioop.avg(cur_data, 4)))
            slid_win.append(level)

            # Only accumulate into the average if we don't believe that
            # someone's talking. Otherwise them talking will push up the
            # threshold and they will just have to keep talking louder and
            # louder, else we'll stop recording.
            if not talking:
                average_win.append(level)            

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

                # See what the top X percent of that looks like.
                count   = int((window_size - slide_size) * 0.25) + 1
                average = numpy.mean(sorted(values, reverse=True)[:count])

                # The threshold at which we denote there to be elevated sound
                # levels or not. If someone is currently talking then we use a
                # lower multipler which they must drop below in order to spot
                # the end of the speech. Detecting the start of the speech has a
                # higher bar.
                if talking:
                    threshold = average * threshold_under
                else:                
                    threshold = average * threshold_over

                # See if it's changed enough lately that we should log it
                if log_threshold <= 0 or \
                   abs((log_threshold - threshold) / log_threshold) > 0.2:
                    LOG.info(
                        "Audio threshold change to %d from %d, "
                        "with an average of %d with talking being %s" %
                        (threshold, log_threshold, average, talking)
                    )
                    log_threshold      = threshold
                    log_threshold_time = now
                elif now - log_threshold_time > 1:
                    LOG.info(
                        "Audio threshold is currently %d, with an average of %d" %
                        (threshold, average)
                    )
                    log_threshold      = threshold
                    log_threshold_time = now

                # Whether someone is likely talking.
                max_level = max(slid_win)
                new_talking = max_level > threshold
                if new_talking:
                    LOG.info( "Detected talking where "
                              "max level and threshold are: %d %d" %
                             (max_level, threshold))
                elif new_talking != talking:
                    LOG.info("Detecting change in sound levels where "
                             "max level and threshold are: %d %d" %
                             (max_level, threshold))

                # And assign
                talking = new_talking

                # Only look to see if someone is speaking if the system is
                # not. Otherwise we will likely hear ourselves.
                if self._state.is_speaking() and talking:
                    talking = False
                    LOG.info("Ignoring talking since audio is being output")

            # If we think someone is talking then
            if talking:
                # Remember the last time that we heard someone talking
                talking_last = now

                # If we don't yet have any audio then we're starting the
                # recording
                if audio is None:
                    # Move the rolling window of recording to be the start of
                    # the audio
                    LOG.info("Starting recording")
                    talking_start = now
                    self._notify(Notifier.ACTIVE)
                    audio = list(prev_audio)
                    prev_audio.clear()

                # Add on what we just recorded
                audio.append(cur_data)

            # We deem that talking is still happening if it started only a
            # little while ago
            elif (((now - talking_start) > self._max_audio or
                   (now - talking_last ) > self._mid_silence_limit) and
                   audio is not None):
                # There's no talking but there us recorded audio. That means
                # someone just stopped talking.
                LOG.info("Finished recording")

                # Turn the audio data into text (hopefully!)
                self._notify(Notifier.WORKING)
                start = time.time()

                # Turn the stream into a list of bytes
                data = b''.join(audio)

                # Maybe save then as a wav file
                self._save_bytes(data)

                # Now decode
                LOG.info("Decoding %0.2fs seconds of audio" %
                         (len(data) / self._width / self._rate))
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
