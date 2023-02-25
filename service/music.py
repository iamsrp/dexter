"""
Base class for various music playing services.
"""

from   dexter.core.audio        import MIN_VOLUME, MAX_VOLUME
from   dexter.core.log          import LOG
from   dexter.core.media_index  import FileMusicIndex, AudioEntry
from   dexter.core.player       import SimpleMP3Player
from   dexter.core.util         import homonize, fuzzy_list_range
from   dexter.service           import Service, Handler, Result
from   fuzzywuzzy               import fuzz
from   threading                import Thread

# ------------------------------------------------------------------------------

class MusicService(Service):
    """
    The base class for playing music on various platforms.
    """
    def __init__(self, name, state, platform):
        """
        @see Service.__init__()

        :type  platform: str
        :param platform:
            The name of the platform that this service streams music from, like
            C{Spotify}, C{Pandora}, C{Edna}, C{Local Disk}, etc.
        """
        super(MusicService, self).__init__(name, state)

        self._platform = platform


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Get stripped text, for matching
        words = [homonize(w) for w in self._words(tokens)]
        LOG.debug("Handling: %s", ' '.join(words))

        # Look for specific control words, doing a fuzzy match for single
        # tokens, but an exact match for the "special" phrases (since they
        # typically come from an unambiguously rendering source).
        if len(words) == 1:
            if   (self._matches(words[0], "stop") or
                  self._matches(words[0], "pause")):
                return self._get_stop_handler(tokens)
            elif (self._matches(words[0], "play") or
                  self._matches(words[0], "unpause")):
                return self._get_play_handler(tokens)
        elif words == ['next', 'song']:
            return self._get_next_song_handler(tokens)
        elif words == ['previous', 'song']:
            return self._get_prev_song_handler(tokens)
        elif words == ['play', 'or', 'pause']:
            return self._get_toggle_pause_handler(tokens)

        # Now some potentially fuzzier matches
        for (get_handler, phrases) in (
                (self._get_next_song_handler, (
                    ('next', 'song'),
                    ('play', 'next', 'song'),
                    ('go',   'forward', 'a', 'song'),
                    ('move', 'forward', 'a', 'song'),
                    ('skip', 'forward', 'a', 'song'),
                )),
                (self._get_prev_song_handler, (
                    ('previous', 'song'),
                    ('play', 'previous', 'song'),
                    ('go',   'back',      'a', 'song'),
                    ('go',   'backwards', 'a', 'song'),
                    ('move', 'back',      'a', 'song'),
                    ('move', 'backwards', 'a', 'song'),
                    ('skip', 'back',      'a', 'song'),
                    ('skip', 'backwards', 'a', 'song'),
                )),
                (self._get_describe_song_handler, (
                    ('identify', 'song'),
                    ('whats', 'this', 'song'),
                    ('what', 'is', ' this', 'song'),
                    ('name', 'this', 'song'),
                )),
        ):
            for phrase in phrases:
                try:
                    (s, e, _) = fuzzy_list_range(words, phrase)
                    if s == 0 and e == len(phrase):
                        return get_handler(tokens)
                except ValueError:
                    pass

        # We didn't match on the stock phrases so move on to trying to see if
        # this is a command to play a song.
        #
        # We expect to have something along the lines of:
        #  Play <song or album> on <platform>
        #  Play <genre> music
        #  Play <song or album> by <artist>
        if len(words) < 3:
            # We can't match on this
            LOG.debug("Can't match on too few words")
            return None

        # See if the first word is "play"
        if not self._matches(words[0], "play"):
            # Nope, probably not ours then
            LOG.debug("'play' not the first word")
            return None

        # Okay, strip off "play"
        words = words[1:]

        # See if it ends with "on <platform>", if so then we can see if it's for
        # us specificaly.
        platform_match = False
        for back in range(-2, -5, -1):
            if self._matches(words[back], "on"):
                # Handle partial matches on the service name since, for example,
                # "spotify" often gets interpreted as "spotty"
                platform = ' '.join(words[back+1:])
                if fuzz.ratio(platform.lower(), self._platform.lower()) > 50:
                    # This is definitely for us
                    platform_match = True
    
                    # Strip off the platfrom now so that we can match other things
                    words = words[:back]
                else:
                    # Looks like it's for a different platform
                    LOG.debug("Given platform '%s' didn't match '%s'",
                              platform, self._platform)
                    return None

                # And whatever happened above we matched to 'on' we we're done
                break

        # See if we have an artist
        artist = None
        if "by" in words and len(words) >= 3:
            # We see if this matches a know artist. It could by something like
            # "Bye Bye Baby" fooling us.

            # Find the last occurance of "by"; hey Python, why no rindex?!
            by_index = len(words) - list(reversed(words)).index("by") - 1
            artist = words[by_index+1:]
            if self._match_artist(artist):
                # Okay, strip off the artist
                words = words[:by_index]
            else:
                # No match
                artist = None

        # See if it ends with a genre indicator. Don't do this if we matched an
        # artist (since it could be "Sexy Music" by "Meat Puppets", for example).
        if artist is None and len(words) > 1 and self._matches(words[-1], "music"):
            genre = tuple(words[:-1])
            words = []
        else:
            genre = None

        # Anything left should be the song-or-album name now
        if len(words) > 0:
            song_or_album = tuple(words)
            words = []

        # Okay, ready to make the hand-off call to the subclass
        LOG.debug("Looking for %s%s with%s platform match",
                  song_or_album,
                  f' by {artist}' if artist is not None else '',
                  '' if platform_match else ' no')
        return self._get_handler_for(tokens,
                                     platform_match,
                                     genre,
                                     artist,
                                     song_or_album)


    def set_volume(self, volume):
        """
        Set the volume to a value between zero and eleven.

        :type  value: float
        :param value:
            The volume level to set. This should be between `MIN_VOLUME` and
            `MAX_VOLUME` inclusive.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def get_volume():
        """
        Get the current volume, as a value between zero and eleven.

        :rtype: float
        :return:
            The volume level; between 0 and 11 inclusive.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def _matches(self, words, target):
        """
        Use fuzz.ratio to match word tuples.
        """
        return fuzz.ratio(words, target) >= 75


    def _match_artist(self, artist):
        """
        See if the given artist name tuple matches something we know about.

        :type  artist: tuple(str)
        :param artist:
            The artist name, as a tuple of strings.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def _get_stop_handler(self, tokens):
        """
        Get the handler to stop playing whatever is playing. If nothing is playing
        then return C{None}.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def _get_play_handler(self, tokens):
        """
        Get the handler to resume playing whatever was playing (and was previously
        stopped). If nothing was playing then return C{None}.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def _get_toggle_pause_handler(self, tokens):
        """
        Get the handler to pause playing whatever is playing, or start playing
        whatever is paused; or nothing is neither is the case.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def _get_next_song_handler(self, tokens):
        """
        Get the handler to move to the next song, if we can.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        """
        # By default we do nothing for this since it might not be supported for
        # certain players
        return None


    def _get_prev_song_handler(self, tokens):
        """
        Get the handler to go back to the previous song, if we can.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        """
        # By default we do nothing for this since it might not be supported for
        # certain players
        return None


    def _get_describe_song_handler(self, tokens):
        """
        Get the handler to describe the song currently playing.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        """
        # By default we do nothing for this since it might not be supported for
        # certain players
        return None


    def _get_handler_for(self,
                         tokens,
                         platform_match,
                         genre,
                         artist,
                         song_or_album):
        """
        Get the handler for the given arguments, if any.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        :type  platform_match: bool
        :param platform_match:
            Whether the platform was specified.
        :type  genre: tuple(str)
        :param genre:
            The music genre type, as a tuple of strings.
        :type  artist: tuple(str)
        :param artist:
            The artist name, as a tuple of strings.
        :type  song_or_album: tuple(str)
        :param song_or_album:
            The name of the song or album to play, as a tuple of strings.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


class MusicServicePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(MusicServicePauseHandler, self).__init__(
            service,
            tokens,
            1.0 if service.is_playing() else 0.0,
            False
        )


    def handle(self):
        """
        @see Handler.handle()
        """
        was_playing = self.service.is_playing()
        self.service.pause()
        return Result(self, '', False, was_playing)


class MusicServiceUnpauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(MusicServiceUnpauseHandler, self).__init__(
            service,
            tokens,
            1.0  if service.is_paused() else 0.0,
            True if service.is_paused() else False,
        )


    def handle(self):
        """
        @see Handler.handle()
        """
        was_paused = self.service.is_paused()
        self.service.unpause()
        return Result(self, '', False, was_paused)


class MusicServiceTogglePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(MusicServiceTogglePauseHandler, self).__init__(
            service,
            tokens,
            1.0  if service.is_paused() or service.is_playing() else 0.0,
            True if service.is_paused() or service.is_playing() else False,
        )


    def handle(self):
        """
        @see Handler.handle()
        """
        if self.service.is_playing():
            self.service.pause()
            handled = True
        elif self.service.is_paused():
            self.service.unpause()
            handled = True
        else:
            handled = False
        return Result(self, '', False, handled)

# ------------------------------------------------------------------------------

class _LocalMusicServicePauseHandler(MusicServicePauseHandler):
    pass


class _LocalMusicServiceUnpauseHandler(MusicServiceUnpauseHandler):
    pass


class _LocalMusicServiceTogglePauseHandler(MusicServiceTogglePauseHandler):
    pass


class _LocalMusicServicePlayHandler(Handler):
    def __init__(self, service, tokens, what, filenames, score):
        """
        @see Handler.__init__()

        :type  what: str
        :param what:
            What we are playing, like "Blah Blah by Fred"
        :type  filenames: list(str)
        :param filenames:
            The list of filenames to play
        :type  score: float
        :param score:
            The match score out of 1.0.
        """
        # We deem ourselves exclusive since we had a match
        super(_LocalMusicServicePlayHandler, self).__init__(
            service,
            tokens,
            score,
            True
        )
        self._filenames = filenames
        self._what      = what


    def handle(self):
        """
        @see Handler.handle()`
        """
        LOG.info('Playing %s' % (self._what))
        self.service.play(self._filenames)
        return Result(self, '', False, True)


class LocalMusicService(MusicService):
    """
    Music service for local files.
    """
    def __init__(self, state, dirname=None):
        """
        @see Service.__init__()

        :type  dirname: str
        :param dirname:
            The directory where all the music lives.
        """
        super(LocalMusicService, self).__init__("LocalMusic",
                                                state,
                                                "Local")

        if dirname is None:
            raise ValueError("Not given a directory name")

        self._player = SimpleMP3Player()

        # Spawn a thread to create the media index, since it can take a long
        # time.
        self._media_index = None
        def create_index():
            try:
                self._media_index = MusicIndex(dirname)
            except Exception as e:
                LOG.error("Failed to create music index: %s", e)
        thread = Thread(name='MusicIndexer', target=create_index)
        thread.daemon = True
        thread.start()


    def set_volume(self, volume):
        """
        @see MusicService.set_volume()
        """
        self._player.set_volume(volume)


    def get_volume():
        """
        @see MusicService.get_volume()
        """
        return self._player.get_volume()


    def play(self, filenames):
        """
        Play the given list of filenames.

        :type  filenames: tuple(str)
        :param filenames:
            The list of filenames to play.
        """
        self._player.play_files(filenames)


    def is_playing(self):
        """
        Whether the player is playing.

        :rtype: bool
        :return:
           Whether the player is playing.
        """
        return self._player.is_playing()


    def is_paused(self):
        """
        Whether the player is paused.

        :rtype: bool
        :return:
           Whether the player is paused.
        """
        return self._player.is_paused()


    def pause(self):
        """
        Pause any currently playing music.
        """
        self._player.pause()


    def unpause(self):
        """
        Resume any currently paused music.
        """
        self._player.unpause()


    def _match_artist(self, artist):
        """
        @see MusicService._match_artist()
        """
        if self._media_index is None:
            return False
        else:
            matches = self._media_index.lookup(artist=' '.join(artist))
            return len(matches) > 0


    def _get_stop_handler(self, tokens):
        """
        @see MusicService._get_stop_handler()
        """
        return _LocalMusicServicePauseHandler(self, tokens)


    def _get_play_handler(self, tokens):
        """
        @see MusicService._get_play_handler()
        """
        return _LocalMusicServiceUnpauseHandler(self, tokens)


    def _get_toggle_pause_handler(self, tokens):
        """
        @see MusicService._get_toggle_pause_handler()
        """
        return _LocalMusicServiceTogglePauseHandler(self, tokens)


    def _get_handler_for(self,
                         tokens,
                         platform_match,
                         genre,
                         artist,
                         song_or_album):
        """
        @see MusicService._get_handler_for()
        """
        if self._media_index is None:
            return None

        # Do nothing if we have no name
        if song_or_album is None or len(song_or_album) == 0:
            return None

        # Normalise to strings
        name = ' '.join(song_or_album)
        if artist is None or len(artist) == 0:
            artist = None
        else:
            artist = ' '.join(artist)

        # Try using the song_or_album as the song name
        entries = self._media_index.lookup(name=name, artist=artist)
        if len(entries) > 0:
            # Just pick the first
            entries = entries[:1]
            entry = entries[0]

            # Score by the song name (this is out of 100)
            score = fuzz.ratio(entry.name, name)
            if score < 50:
                # Not a good enough match, blank the list and try more below
                entries = []
            else:
                # What we are playing
                what = entry.name
                if entry.artist is not None:
                    what += ' by ' + entry.artist

        
        # If that failed then fall back to it being the album name
        if len(entries) == 0:
            entries = self._media_index.lookup(album=name, artist=artist)
            if len(entries) > 0:
                # Score by the album name (this is also out of 100)
                score = fuzz.ratio(entries[0].album, name)
                if score < 50:
                    # Not a good enough match, blank the list
                    entries = []
                else:
                    # What we are playing
                    what = entries[0].album
                    if entries[0].artist is not None:
                        what += ' by ' + entries[0].artist

        # Strip out any entries which aren't MP3 files
        entries = [entry
                   for entry in entries
                   if (entry.url.startswith('file://') and
                       entry.file_type == AudioEntry.MP3)]

        # See if we got anything
        if len(entries) > 0:
            return _LocalMusicServicePlayHandler(
                self,
                tokens,
                what,
                [entry.url[7:] for entry in entries],
                score / 100.0
            )
        else:
            return None
