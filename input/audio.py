"""
Input using audio data from the microphone.
"""

from   collections     import deque
from   dexter.input    import Input, Token
from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   threading       import Thread

import audioop
import math
import numpy
import os
import pyaudio
import time
import wave

# ------------------------------------------------------------------------------

class AudioInput(Input):
    """
    Base class for input from audio.
    """
    _GOBBLE_LIMIT = 15
    """
    How many seconds old a clip is before we throw it away. This can happen if
    decoding has fallen behind for some reason.
    """

    def __init__(self,
                 state,
                 chunk_secs=0.1,
                 format    =pyaudio.paInt16,
                 channels  =1,
                 rate      =16000,
                 wav_dir   =None):
        """
        :type  state: L{State}
        :param state:
            The State instance.
        :type  chunk_secs: float
        :param chunk_secs:
            The length of a read chunk.
        :type  format: int
        :param format:
            The pyaudio format.
        :type  channels: int
        :param channels:
            The number of audio channels (typically 1).
        :type  rate: int
        :param rate:
            The sample rate. This is usually 16kHz for many speech to text
            systems.
        :type  wav_dir: str
        :param wav_dir:
            Where to save WAV files to, if we are doing so.
        """
        super(AudioInput, self).__init__(state)

        # Microphone stream config
        self._format     = format
        self._channels   = channels
        self._width      = pyaudio.get_sample_size(pyaudio.paInt16) * channels
        self._rate       = rate
        self._chunk_size = int(chunk_secs     *
                               self._channels *
                               self._width    *
                               self._rate) # makes chunk_size in bytes

        # How we hand off to another thread to decode and handle asynchronously
        self._decode_queue    = deque()
        self._max_queue_lenth = 100

        # Where to save the wav files, if anywhere. This should already exist.
        if wav_dir is not None and not os.path.isdir(wav_dir):
            raise IOError("Not a directory: %s" % wav_dir)
        self._wav_dir = wav_dir

        # What we receive
        self._output = list()


    def read(self):
        """
        @see Input.read
        """
        if len(self._output) > 0:
            try:
                return self._output.pop()
            except:
                pass
        return None


    def _start(self):
        """
        @see Component._start()
        """
        # Start the component's worker threads
        thread = Thread(target=self._run)
        thread.daemon = True
        thread.start()

        thread = Thread(target=self._handler)
        thread.daemon = True
        thread.start()


    def _save_bytes(self, data):
        """
        Save the raw bytes to a wav file.

        :type  data: str
        :param data:
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


    def _feed_raw(self, data):
        """
        Feed a chunk of raw data to the decoder.

        :type  data: str.
        :param data:
            The bytes to save decode.
        """
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


    def _decode(self):
        """
        Decode the raw fed data.

        :rtype: tuple(L{Token})
        :return:
           The decoded tokens.
        """
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


    def _run(self):
        """
        Reads from the audio input stream and hands it off to be processed.
        """
        # This possibly takes a while so tell the system what we're doing.
        self._notify(Notifier.INIT)

        # The number of read calls which we expect per second. This corresponds
        # to many entries in a buffer constitute a second's worth of data.
        read_rate = self._rate / self._chunk_size

        # The buffer of historical audio data. We use the level buffer
        # to see how the sound is changing.
        level_buf = deque(maxlen=int(4.0 * read_rate))

        # The index from the level buffer's end at which we cut the
        # level buffer for the purposes of looking for a change in the
        # audio going from background to noisy, or vice versa. This is
        # what we are looking for when detecting to start or end of
        # speech input.
        avg_idx = level_buf.maxlen // 3

        # The audio buffer captures the sound up to before we decide
        # to start recording, so that we ensure we've captured
        # enough. We use the detected start of speech as the size, or
        # a second, whichever is the bigger.
        audio_buf = deque(maxlen=max(avg_idx, int(1.0 * read_rate)))

        # Start pulling in the audio stream
        p      = pyaudio.PyAudio()
        stream = p.open(format           =self._format,
                        channels         =self._channels,
                        rate             =self._rate,
                        input            =True,
                        frames_per_buffer=self._chunk_size)

        # State
        talking = None  # True when we have detect talking
        speech  = None  # What we will process as speech data

        # Limits on recording
        min_secs =  2 # <-- Enough for the key-phrase only
        max_secs = 10 # <-- Plenty?

        # Init is done, we start off idle
        self._notify(Notifier.IDLE)

        # Keep listening until we are stopped
        while self.is_running:
            # We'll need this here and there below
            now = time.time()

            # Read in the next lump of data and get its volume. It looks like
            # rms() is the the best measure of this but I could be wrong.
            chunk = stream.read(self._chunk_size, exception_on_overflow=False)
            level = abs(audioop.rms(chunk, self._width))

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

            # We are looking for the background levels. If we think that someone
            # is talking then the background sound going to be at the end of the
            # levels, else it will be at the start.

            # Get the median level as we transition
            from_levels = levels[        :-avg_idx] # From start to avg_idx
            to_levels   = levels[-avg_idx:        ] # From avg_idx to end
            from_median = numpy.sort(from_levels)[int(len(from_levels) * 0.5)]
            to_median   = numpy.sort(to_levels  )[int(len(to_levels  ) * 0.5)]
            LOG.debug("Levels are from=%0.2f to=%0.2f", from_median, to_median)

            # Different detection based on what we are looking for
            if not talking:
                # Looking for a step up in the latter part
                if from_median * 2.0 < to_median:
                    LOG.info("Detected start of speech "
                             "with levels going from %0.2f to %0.2f" %
                             (from_median, to_median))
                    talking = True
                    talking_start = now
                    start_median = from_median
            else:
                # Looking for a step down in the latter part
                if (now - talking_start > min_secs and
                    (from_median > to_median * 1.5 or to_median < start_median * 1.1)):
                    LOG.info("Detected end of speech "
                             "with levels going from %0.2f to %0.2f (start %0.2f)" %
                             (from_median, to_median, start_median))
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
                    speech = []

                    # Start off by putting the current time on the queue, so the
                    # recipient knows how old this data is when it gets it.
                    self._decode_queue.append(time.time())

                    # Push in everything that we have
                    while audio_buf:
                        prev = audio_buf.popleft()
                        speech.append(prev)
                        self._decode_queue.append(prev)
                else:
                    # Add on what we just recorded
                    speech.append(chunk)
                    self._decode_queue.append(chunk)

            # We deem that talking is still happening if it started only a
            # little while ago
            elif speech is not None:
                # There's no talking but there is recorded audio. That means
                # someone just stopped talking.
                LOG.info("Finished recording")

                # Turn the stream into a list of bytes and junk the speech
                # buffer
                audio  = b''.join(speech)
                speech = None

                # Maybe save then as a wav file
                self._save_bytes(audio)

                # Now decode. We do this by denoting the end of the audio with a None.
                self._decode_queue.append(None)

                # Ensure the old queue is empty before we start again
                audio_buf.clear()

                # And we're back to listening
                LOG.info("Listening")

        # If we got here then _running was set to False and we're done
        LOG.info("Done listening")
        self._decode_queue = None
        stream.close()
        p.terminate()


    def _handler(self):
        """
        Pulls values from the decoder queue and handles them appropriately. Runs in
        its own thread.
        """
        # Whether we are skipping the current input
        gobble = False

        LOG.info("Started decoding handler")
        while True:
            try:
                # Get a handle on the queue. This will be nulled out when we're
                # done.
                queue = self._decode_queue
                if queue is None:
                    break

                # Anything?
                if len(queue) > 0:
                    item = queue.popleft()
                    if item is None:
                        # A None denotes the end of the data so we look to
                        # decode what we've been given if we're not throwing it
                        # away.
                        if gobble:
                            LOG.info("Dropped audio")
                        else:
                            LOG.info("Decoding audio")
                            self._notify(Notifier.WORKING)
                            self._output.append(self._decode())
                            self._notify(Notifier.IDLE)
                    elif isinstance(item, float) :
                        # This is the timestamp of the clip. If it's too old
                        # then we throw it away.
                        age = time.time() - item
                        if int(age) > 0:
                            LOG.info("Upcoming audio clip is %0.2fs old" % (age,))
                        gobble = age > self._GOBBLE_LIMIT
                    elif isinstance(item, bytes):
                        # Something to feed the decoder
                        if gobble:
                            LOG.debug("Ignoring %d bytes" % len(item))
                        else:
                            LOG.debug("Feeding %d bytes" % len(item))
                            self._feed_raw(item)
                    else:
                        LOG.warning("Ignoring junk on decode queue: %r" % (item,))

                    # Go around again
                    continue

            except Exception as e:
                # Be robust but log it
                LOG.error("Got an error in the decoder queue: %s" % (e,))

            # Don't busy-wait
            time.sleep(0.001)

        # And we're done!
        LOG.info("Stopped decoding handler")


class _Future(object):
    """
    A simple future, for returning a result.
    """
    def __init__(self):
        self._result = None
        self._ready  = False


    def set_result(self, result):
        """
        Set the result.
        """
        self._result = result
        self._ready  = True


    def get_result(self):
        """
        Get the result, blocking until it's ready.

        If the result was an exception then it will be thrown.
        """
        while True:
            if self._ready:
                if isinstance(self._result, Exception):
                    raise self._result
                else:
                    return self._result
            time.sleep(0.001)
