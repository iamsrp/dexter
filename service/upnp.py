"""
Classes for UPnP services.
"""

from   dexter.core.audio        import MIN_VOLUME, MAX_VOLUME
from   dexter.core.log          import LOG
from   dexter.core.media_index  import MusicIndex, AudioEntry
from   dexter.core.util         import homonize, fuzzy_list_range
from   dexter.service           import Service, Handler, Result
from   didl_lite                import didl_lite
from   fnmatch                  import fnmatch
from   fuzzywuzzy               import fuzz
from   threading                import Thread
from   .music                   import MusicService

import time
import upnpy
import vlc

# ------------------------------------------------------------------------------

# We'll use VLC as the player for the UPnP music service. This might be handy
# elsewhere, so we may choose to move it out at some point.

class _VlcMusicServicePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super().__init__(
            service,
            tokens,
            1.0 if service.is_playing() else 0.0,
            True
        )


    def handle(self):
        """
        @see Handler.handle()
        """
        was_playing = self.service.is_playing()
        self.service.pause()
        return Result(self, '', False, was_playing)


class _VlcMusicServiceUnpauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super().__init__(
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


class _VlcMusicServiceTogglePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super().__init__(
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


class _VlcMusicServicePlayHandler(Handler):
    def __init__(self, service, tokens, what, urls, score):
        """
        @see Handler.__init__()

        :type  what: str
        :param what:
            What we are playing, like "Blah Blah by Fred"
        :type  urls: list(str)
        :param urls:
            The list of URLs to play.
        :type  score: float
        :param score:
            The match score out of 1.0.
        """
        # We deem ourselves exclusive since we had a match
        super().__init__(
            service,
            tokens,
            score,
            True
        )
        self._urls = urls
        self._what = what


    def handle(self):
        """
        @see Handler.handle()
        """
        LOG.info('Playing %s' % (self._what))
        self.service.play(self._urls)
        return Result(self, '', False, True)


class _VlcMusicService(MusicService):
    """
    Music service for local files.
    """
    def __init__(self, name, state, platform):
        """
        @see Service.__init__()
        """
        super().__init__(name, state, platform)

        self._vlc_instance      = vlc.Instance()
        self._media_player      = self._vlc_instance.media_player_new()
        self._media_list_player = self._vlc_instance.media_list_player_new()


    def set_volume(self, volume):
        """
        @see MusicService.set_volume()
        """
        self._media_player.audio_set_volume(
            min(100, max(0, int((volume - MIN_VOLUME) / MAX_VOLUME * 100)))
        )


    def get_volume():
        """
        @see MusicService.get_volume()
        """
        return int(
            self._media_player.audio_get_volume() /
            100 * (MAX_VOLUME - MIN_VOLUME) +
            MIN_VOLUME
        )


    def play(self, urls):
        """
        Play the given list of urls.

        :type  urls: tuple(str)
        :param urls:
            The list of urls to play.
        """
        # Make a new media list and add all the URLs to it
        ml = self._vlc_instance.media_list_new()
        ml.lock()
        try:
            for url in urls:
                ml.add_media(url)
        finally:
            ml.unlock()

        # Stop anything currently playing, set the new media list into place,
        # and start playing it
        self._media_list_player.stop()
        self._media_list_player.set_media_list(ml)
        self._media_list_player.play()


    def is_playing(self):
        """
        Whether the player is playing.

        :rtype: bool
        :return:
           Whether the player is playing.
        """
        return self._media_list_player.get_state() == vlc.State.Playing


    def is_paused(self):
        """
        Whether the player is paused.

        :rtype: bool
        :return:
           Whether the player is paused.
        """
        return self._media_list_player.get_state() == vlc.State.Paused


    def pause(self):
        """
        Pause any currently playing music.
        """
        self._media_list_player.set_pause(True)


    def unpause(self):
        """
        Resume any currently paused music.
        """
        self._media_list_player.set_pause(False)


    def _get_stop_handler(self, tokens):
        """
        @see MusicService._get_stop_handler()
        """
        return _VlcMusicServicePauseHandler(self, tokens)


    def _get_play_handler(self, tokens):
        """
        @see MusicService._get_play_handler()
        """
        return _VlcMusicServiceUnpauseHandler(self, tokens)


    def _get_toggle_pause_handler(self, tokens):
        """
        @see MusicService._get_toggle_pause_handler()
        """
        return _VlcMusicServiceTogglePauseHandler(self, tokens)

# ------------------------------------------------------------------------------

class _UpnpMusicIndex(MusicIndex):
    def __init__(self, device, globs):
        """
        Build the music index on the given device, filtering by the globs if given.
        """
        super().__init__()

        self._device = device
        self._globs  = globs


    def create(self):
        """
        Build the index
        """
        LOG.info("Indexing %s", self._device)
        start = time.time()
        self._get_songs(self._device, self._globs)
        end = time.time()
        LOG.info("Done indexing %s in %ds; got %d entries",
                 self._device, end - start, self._count)


    def _get_songs(self,
                   device,
                   globs,
                   seen     =set(),
                   dirname  ='',
                   object_id='0'):
        """
        Recurse into the device, walking down the ContentDirectory tree.
        """
        LOG.info(f"Retrieving '{device.friendly_name}':/{dirname}")
        try:
            data = device.ContentDirectory.Browse(
                       Filter        ='*',
                       ObjectID      =object_id,
                       BrowseFlag    ='BrowseDirectChildren',
                       StartingIndex ='0',
                       RequestedCount='-1',
                       SortCriteria  =''
                   )
            entries = didl_lite.from_xml_string(data['Result'],
                                                strict=False)
        except Exception as e:
            LOG.warning("Failed to browse %s: %s", dirname, e)
            return

        # Okay, let's parse them
        for entry in entries:
            # Create the path
            basename = entry.title.replace("/", "|")
            if dirname:
                path = f'{dirname}{basename}'
            else:
                path = f'{basename}'

            # Different actions depending on what we have
            if isinstance(entry, didl_lite.StorageFolder):
                # Recurse into folder?
                path += '/'
                if (globs is None or
                    any(len(glob.split('/')) > len(path.split('/')) or
                        fnmatch(path, glob)
                        for glob in globs)):
                    self._get_songs(device,
                                    globs,
                                    seen     =seen,
                                    dirname  =path,
                                    object_id=entry.id)
            elif isinstance(entry, didl_lite.MusicTrack):
                # Parse song info?
                name   = (getattr(entry, 'title',  '') or '').strip()
                artist = (getattr(entry, 'artist', '') or '').strip()
                song_id = f'{path}/{artist}/{name}'
                if song_id not in seen:
                    seen.add(song_id)
                    try:
                        self._add_entry(AudioEntry.from_music_track(entry))
                    except Exception as e:
                        LOG.warning("Failed to index %s: %s", song_id, e)


class UpnpMusicService(_VlcMusicService):
    """
    Music service for UPnP sources.

    This requires ``python-vlc`` to be installed.
    """
    def __init__(self, state,
                 server_name,
                 alias=None,
                 globs=None):
        """
        @see Service.__init__()

        :type  server_name: str
        :param server_name:
            The name of the server to traverse.
        :type  alias: str
        :param alias:
            The name to call the music service, if not the ``server_name`` value
            or ``U P N P``.
        :type  globs: list(str)
        :param globs:
            Any matches to use when traversing the directory hierarchies in the
            DLNA servers. Ignored if ``None``.
        """
        super().__init__("UpnpMusic",
                         state,
                         alias or server_name or "U P N P")

        if not server_name:
            raise ValueError("server_name not given")

        if globs is not None:
            if not isinstance(globs, (list, tuple)):
                globs = [globs]

        self._globs       = globs
        self._server_name = server_name
        self._server      = None
        self._media_index = None


    def _start(self):
        """
        @see Service._start()
        """
        super()._start()

        # Look for what we have sitting on the network
        LOG.info("Looking for UPnP devices...")
        upnp = upnpy.UPnP()
        devices = {str(d) : d for d in upnp.discover()}
        if len(devices) == 0:
            raise ValueError("No UPnP devices found");
        names = []
        LOG.info("  Found:")
        for d in devices.values():
            names.append(d.friendly_name)
            LOG.info(f"    {d.friendly_name}")
            for s in d.get_services():
                LOG.info(f"      {s.id}")

        # Find the server device which we want
        for d in devices.values():
            if self._server_name == d.friendly_name:
                self._server = d
                break

        # Make sure we got the server and that it has the services which we want
        # (right now just one)
        if self._server is None:
            raise ValueError(
                "Could not find DLNA server '%s' in: " %
                (self._server_name, ", ".join(names))
            )
        for svc in ('ContentDirectory',):
            if not hasattr(self._server, svc):
                raise ValueError(
                    "Server '%s' is missing service '%s'" %
                    (self._server_name, svc)
                )

        # Spawn a thread to create the media index, since it can take a long
        # time
        self._media_index = _UpnpMusicIndex(self._server, self._globs)
        def create_index():
            try:
                self._media_index.create()
            except Exception as e:
                LOG.error("Failed to create music index from %s: %s",
                          self._server, e)
        thread = Thread(name='MusicIndexer', target=create_index)
        thread.daemon = True
        thread.start()


    def _match_artist(self, artist):
        """
        @see MusicService._match_artist()
        """
        if self._media_index is None:
            return False
        else:
            matches = self._media_index.lookup(artist=' '.join(artist))
            return len(matches) > 0


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
            LOG.info("No media index")
            return None

        # Do nothing if we have no name
        if song_or_album is None or len(song_or_album) == 0:
            LOG.info("No song or album given")
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

        # If we got anything then choose the first one
        if len(entries) > 0:
            LOG.info("Found entries: %s", ', '.join(str(e) for e in entries))
            return _VlcMusicServicePlayHandler(
                self,
                tokens,
                what,
                [e.url for e in entries],
                score / 100.0
            )
        else:
            LOG.info("Matched no entries")
            return None
