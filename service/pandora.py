"""
A simple Pandora client, using `pydora` under the hood. 

Before you can use this you will need to run ``pydora-configure`` to, err,
configure `pydora`.
"""

from   dexter.core.audio        import MIN_VOLUME, MAX_VOLUME
from   dexter.core.log          import LOG
from   dexter.service           import Service, Handler, Result
from   pandora                  import clientbuilder
from   pydora.audio_backend     import VLCPlayer
from   threading                import Thread
from   .music                   import MusicService

import sys

# ------------------------------------------------------------------------------

class _PandoraServicePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_PandoraServicePauseHandler, self).__init__(
            service,
            tokens,
            1.0 if service.is_playing() else 0.0,
            False
        )


    def handle(self):
        """
        @see Handler.handle()`
        """
        try:
            was_playing = self.service.is_playing()
            self.service.pause()
            return Result(self, '', False, was_playing)
        except:
            return Result(self, '', False, False)


class _PandoraServiceUnpauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_PandoraServiceUnpauseHandler, self).__init__(
            service,
            tokens,
            1.0,
            True
        )


    def handle(self):
        """
        @see Handler.handle()`
        """
        try:
            self.service.unpause()
            return Result(self, '', False, True)
        except:
            return Result(self, '', False, False)


class _PandoraServiceTogglePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_PandoraServiceTogglePauseHandler, self).__init__(
            service,
            tokens,
            1.0,
            True
        )


    def handle(self):
        """
        @see Handler.handle()`
        """
        try:
            if self.service.is_playing():
                self.service.pause()
            else:
                self.service.unpause()
            return Result(self, '', False, True)
        except Exception as e:
            return Result(self, '', False, False)


class _PandoraServicePlayHandler(Handler):
    def __init__(self, service, tokens, what, token, score):
        """
        @see Handler.__init__()

        :type  what: str
        :param what:
            What we are playing, like "Blah Blah by Fred"
        :type  token: str
        :param token:
            The token from the search.
        :type  score: float
        :param score:
            The match score out of 1.0.
        """
        # We deem ourselves exclusive since we had a match
        super(_PandoraServicePlayHandler, self).__init__(
            service,
            tokens,
            score,
            True
        )
        self._token = token
        self._what  = what


    def handle(self):
        """
        @see Handler.handle()`
        """
        LOG.info('Playing %s' % (self._what))
        self.service.play(self._token)
        return Result(self, '', False, True)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

class Callbacks():
    """
    The player callback handlers.
    """
    def __init__(self, service):
        self._service = service

    def play(self, song):
        LOG.info("Playing %s", song)


    def pre_poll(self):
        # Can be ignored
        pass


    def post_poll(self):
        # Can be ignored
        pass


    def input(self, cmd, song):
        LOG.error("Got command '%s' for song '%s'", cmd, song)
                  
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

class PandoraService(MusicService):
    """
    Music service for local files.
    """
    def __init__(self, state, config_file=''):
        """
        @see Service.__init__()

        :type  config_file: str
        :param config_file:
            The path to the config file, if not the default.
        """
        super(PandoraService, self).__init__("PandoraService",
                                             state,
                                             "Pandora")

        self._config_file = config_file
        self._pandora     = None
        self._player      = None
        self._station     = None


    def set_volume(self, volume):
        """
        @see MusicService.set_volume()
        """
        if MIN_VOLUME <= volume <= MAX_VOLUME:
            self._player._send_cmd('volume %d' % (
                100.0 * (volume - MIN_VOLUME) / (MAX_VOLUME - MIN_VOLUME)
            ))
        else:
            raise ValueError("Bad volume: %s", volume)


    def get_volume():
        """
        @see MusicService.get_volume()
        """
        return self._player._send_cmd('volume')


    def is_playing(self):
        """
        Whether the player is playing.

        :rtype: bool
        :return:
           Whether the player is playing.
        """
        try:
            return int(self._player._send_cmd('is_playing'))
        except:
            return False


    def play(self, token):
        """
        Set the song(s) to play.
        """
        # Out with the old
        if self._station is not None:
            try:
                self._player.end_station()
            except:
                pass
            self._pandora.delete_station(self._station.token)

        # In with the new
        self._station = self._pandora.create_station(search_token=token)
        LOG.error("Playing station %s", self._station)

        # And play it, in a new thread since it is blocking
        thread = Thread(target=self._play_station)
        thread.daemon = True
        thread.start()


    def pause(self):
        """
        Pause any currently playing music.
        """
        self._player.stop()
        self._player.end_station()


    def unpause(self):
        """
        Resume any currently paused music.
        """
        self._player._send_cmd('play')


    def _start(self):
        """
        @see Startable._start()
        """
        builder = clientbuilder.PydoraConfigFileBuilder('')
        if not builder.file_exists:
            raise ValueError("Unable to find config file; "
                             "have you run pydora-config yet?")

        self._pandora = builder.build()
        LOG.info("Configured as device %s", self._pandora.device)

        self._player = VLCPlayer(Callbacks(self), sys.stdin)
        self._player.start()


    def _stop(self):
        """
        @see Startable._stop()
        """
        # Be tidy
        if self._station is not None:
            self._player.end_station()
            self._pandora.delete_station(self._station.token)
        self._station = None
            

    def _match_artist(self, artist):
        """
        @see MusicService._match_artist()
        """
        # Do a search and look for a "likely" artist match
        artist = ' '.join(artist)
        result = self._pandora.search(artist)
        return any(item.likely_match for item in result.artists)


    def _get_stop_handler(self, tokens):
        """
        @see MusicService._get_stop_handler()
        """
        return _PandoraServicePauseHandler(self, tokens)


    def _get_play_handler(self, tokens):
        """
        @see MusicService._get_play_handler()
        """
        return _PandoraServiceUnpauseHandler(self, tokens)


    def _get_toggle_pause_handler(self, tokens):
        """
        @see MusicService._get_toggle_pause_handler()
        """
        return _PandoraServiceTogglePauseHandler(self, tokens)


    def _get_handler_for(self,
                         tokens,
                         platform_match,
                         genre,
                         artist,
                         song_or_album):
        """
        @see MusicService._get_handler_for()
        """
        # Do nothing if we have no name
        if song_or_album is None or len(song_or_album) == 0:
            return None

        # Normalise to strings
        name = ' '.join(song_or_album)
        if artist is None or len(artist) == 0:
            artist = None
        else:
            artist = ' '.join(artist)

        # Construct the search string
        search = name
        if artist is not None:
            search += " by " + artist

        # Do the search
        LOG.error("Looking for '%s'", search)
        result = self._pandora.search(search)
        LOG.error("Got: %s", result)

        # See if we got something back
        if len(result.songs) > 0:
            # Pick the best
            song  = sorted(result.songs,
                           key=lambda item: item.score,
                           reverse=True)[0]

            # Grab what the handler needs
            what  = "%s by %s" % (song.song_name, song.artist)
            score = song.score / 100.0
            token = song.token

            # And give back the handler to play it
            return _PandoraServicePlayHandler(self, tokens, what, token, score)

        else:
            # We got nothing
            return None


    def _play_station(self):
        """
        Play the current station. This blocks.
        """
        if self._station is not None:
            self._player.play_station(self._station)

