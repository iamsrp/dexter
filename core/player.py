"""
How we play media (like music).
"""

from   dexter.core.audio import MIN_VOLUME, MAX_VOLUME
from   dexter.core.log   import LOG
from   dexter.core.util  import get_pygame()
from   threading         import Thread

import queue
import time

# ------------------------------------------------------------------------------

class SimpleMP3Player(object):
    """
    A simple mp3 layer, local files only.
    """
    def __init__(self):
        """
        Constructor.
        """
        # What we're playing, and what we've played. These are all filenames.
        self._queue = queue.Queue()

        # If we're paused
        self._paused = False

        # Set the controller thread going
        thread = Thread(target=self._controller)
        thread.daemon = True
        thread.start()


    def set_volume(self, volume):
        """
        Set the volume to a value between zero and eleven.

        :type  value: float
        :param value:
            The volume level to set. This should be between `MIN_VOLUME` and
            `MAX_VOLUME` inclusive.
        """
        volume = float(value)

        if volume < MIN_VOLUME or volume > MAX_VOLUME:
            raise ValueError("Volume out of [%d..%d] range: %s" %
                             (MIN_VOLUME, MAX_VOLUME, value))

        # Set as a fraction of 1
        v = (volume / MAX_VOLUME)
        LOG.info("Setting volume to %0.2f" % v)
        get_pygame().mixer.music.set_volume(v)


    def get_volume(self):
        """
        Get the current volume, as a value between zero and eleven.

        :rtype: float
        :return:
            The volume level; between `MIN_VOLUME` and `MAX_VOLUME` inclusive.
        """
        return MAX_VOLUME * get_pygame().mixer.music.get_volume()


    def is_playing(self):
        """
        Return whether we are currently playing anything.

        :rtype: bool
        :return:
           Whether the player is playing.
        """
        return get_pygame().mixer.music.get_busy() and not self._paused


    def is_paused(self):
        """
        Return whether we are currently paused.

        :rtype: bool
        :return:
           Whether the player is paused.
        """
        return self._paused


    def play_files(self, filenames):
        """
        Play a list of files.

        :type  filenames: tuple(str)
        :param filenames:
            The list of filenames to play.
        """
        # First we stop everything
        self.stop()

        # Make sure that we have at least one file
        if len(filenames) == 0:
            return

        # Now we load the first file. We do this directly so that errors may
        # propagate.
        filename = filenames[0]
        LOG.info("Playing %s", filename)
        get_pygame().mixer.music.load(filename)
        get_pygame().mixer.music.play()

        # And enqueue the rest
        for filename in filenames[1:]:
            self._queue.put(filename)


    def stop(self):
        """
        Stop all the music and clear the queue.
        """
        # If we're stopped then we're not paused
        self._paused = False

        # Empty the queue by replacing the current one with an empty one.
        self._queue = queue.Queue()

        # Tell pygame to stop playing any current music
        try:
            get_pygame().mixer.music.stop()
        except:
            pass


    def pause(self):
        """
        Pause any currently playing music.
        """
        if self.is_playing():
            self._paused = True
            get_pygame().mixer.music.pause()


    def unpause(self):
        """
        Resume any currently paused music.
        """
        self._paused = False
        get_pygame().mixer.music.unpause()


    def _controller(self):
        """
        The main controller thread. This handles keeping things going in the
        background. It does not do much heavy lifting however.
        """
        while True:
            # Tum-ti-tum
            time.sleep(0.1)

            # Do nothing while the song is playing.
            if get_pygame().mixer.music.get_busy():
                continue

            # Get the next song to play, this will block
            song = self._queue.get()
            LOG.info("Playing %s", song)

            # Attempt to play it
            try:
                get_pygame().mixer.music.load(song)
                get_pygame().mixer.music.play()
            except Exception as e:
                LOG.warning("Failed to play %s: %s", song, e)
