"""
A simple Spotify controller client, using `spotipy` under the hood. This
should be considered to be beta quality right now.

This doesn't actually play music itself but, instead, allows you to control a
player.

In order to make this work you will need Spotify Premium, and to set up an
"application" via the ``My Dashboard`` on the Spotify developer webpages. This
will require getting the following::
  * Client ID
  * Client Secret
  * Redirect URI

The Redirect URI should include a port, e.g. ``http://localhost:8765``, to make
things work more seamlessly with this client. When you first start a session you
will need to authenticate you'll see a ``https://accounts.spotify.com/...`` URL
in Dexter's output which, when opened, will redirect to a URL which starts with
the Redirect URI. If a browser pops up (on the local machine's display) then it
will have queried the client and you should be set. Else you can simply do that
via ``curl 'http://localhost:8765/...'``. Once you've authenticate once then you
will have a ``.cache`` file which will be used next time around. The ``.cache``
file can also be copied from machine to machine, so it can work to authenticate
on one with a web browser and copy file to one without.

This is all explained pretty well in the Spotipy docs:
    https://spotipy.readthedocs.io/

In terms of players, if the ``device_name`` is not set then it will pick up
whatever it finds to be the current "default" active device. As well as the
Spotify web player, there are various other ones like::
  * https://github.com/dtcooper/raspotify
  * https://github.com/Spotifyd/spotifyd
  * https://github.com/hrkfdn/ncspot [untested]

On Ubuntu and Raspbian spotifyd works fine to. Only setting the following
variables in the config file seems to be sufficient::

 * username
 * password
 * backend
 * mixer
 * device_name
 * bitrate
 * no_audio_cache
 * initial_volume
 * volume_normalisation
 * normalisation_pregain
 * device_type
I used the defaults in the README for everything except username, password and
device_name.  To point Dexter at it you can set the device name to something
like this (depending on what you set ``device_name`` to be in the config file):
  ``"device_name"   : "dexter"``
It then basically Just Works.

The raspotify package, as is claimed, basically "Just Works" on a Raspberry
Pi. However you might need to do the following to make it "Just Work" for
Dexter:
  1. If the audio doesn't work then you might need to put your ALSA config
     into ``/etc/asoundrc``. See also the Troubleshooting section of the
     package's README.
  2. If you want to always connect to that instance (likely) then you should
     set the ``device_name`` something like this:
       ``"device_name"   : "raspotify (${HOSTNAME})"``
     where that name is the default. You can also set a specific name in the
     ``/etc/default/raspotify`` file and use that too.
"""

from   dexter.core.audio        import MIN_VOLUME, MAX_VOLUME
from   dexter.core.log          import LOG
from   dexter.core.util         import homonize, fuzzy_list_range
from   dexter.service           import Service, Handler, Result
from   fuzzywuzzy               import fuzz
from   math                     import sqrt
from   spotipy                  import Spotify
from   spotipy.oauth2           import SpotifyOAuth
from   .music                   import MusicService

# ------------------------------------------------------------------------------

class _SpotifyServicePauseHandler(Handler):
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
        @see Handler.handle()`
        """
        try:
            was_playing = self.service.is_playing()
            self.service.pause()
            return Result(self, '', False, was_playing)
        except:
            return Result(self, '', False, False)


class _SpotifyServiceUnpauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super().__init__(
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


class _SpotifyServiceTogglePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super().__init__(
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


class _SpotifyServicePlayHandler(Handler):
    def __init__(self, service, tokens, what, uris, score):
        """
        @see Handler.__init__()

        :type  what: str
        :param what:
            What we are playing, like "Blah Blah by Fred"
        :type  uris: list(str)
        :param uris:
            The list of URIs to play.
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
        self._uris = uris
        self._what = what


    def handle(self):
        """
        @see Handler.handle()`
        """
        LOG.info('Playing %s' % (self._what))
        self.service.play(self._uris)
        return Result(self, '', False, True)


class _SpotifyServiceNoMatchHandler(Handler):
    def __init__(self, service, tokens, what):
        """
        @see Handler.__init__()

        :type  what: str
        :param what:
            What we tried to match, like "Blah Blah by Fred"
        """
        # We deem ourselves exclusive since we had a match
        super().__init__(
            service,
            tokens,
            0, # Zero score since we didn't match
            True
        )
        self._what = what


    def handle(self):
        """
        @see Handler.handle()`
        """

        return Result(
            self,
            'Sorry, I could not find %s' % self._what,
            False,
            True
        )

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

class SpotifyService(MusicService):
    """
    Spotify client music service.
    """
    def __init__(self, state,
                 client_id      =None,
                 client_secret  =None,
                 redirect_uri   =None,
                 device_name    =None,
                 match_threshold=75):
        """
        @see Service.__init__()

        For the real meanings of the kwargs, read the Spotipy documentation:
            https://spotipy.readthedocs.io
        You can also set them as the environment variables::
          * ``SPOTIPY_CLIENT_ID``
          * ``SPOTIPY_CLIENT_SECRET``
          * ``SPOTIPY_REDIRECT_URI``

        :type  client_id: str
        :param client_id:
            The Spotify client ID.
        :type  client_secret: str
        :param client_secret:
            The Spotify client secret.
        :type  redirect_uri: str
        :param redirect_uri:
            The Spotify redirect URI.
        :type  device_name: str
        :param device_name:
            The name of the device to control, if not the default one.
        :type  match_threshold: int
        :param match_threshold:
            The fuzzy match threshold to use when trying to match
            song/album/artist names.
        """
        super().__init__("SpotifyService",
                         state,
                         "Spotify")

        self._client_id       = str(client_id)
        self._client_secret   = str(client_secret)
        self._redirect_uri    = str(redirect_uri)
        self._device_name     = str(device_name) if device_name else None
        self._match_threshold = int(match_threshold)
        self._device_id       = None
        self._spotify         = None
        self._volume          = None


    def set_volume(self, volume):
        """
        @see MusicService.set_volume()
        """
        if MIN_VOLUME <= volume <= MAX_VOLUME:
            self._volume = volume
            self._spotify.volume(
                100.0 * (volume - MIN_VOLUME) / (MAX_VOLUME - MIN_VOLUME),
                device_id=self._device_id
            )
        else:
            raise ValueError("Bad volume: %s", volume)


    def get_volume():
        """
        @see MusicService.get_volume()
        """
        return self._volume


    def is_playing(self):
        """
        Whether the player is playing.

        :rtype: bool
        :return:
           Whether the player is playing.
        """
        try:
            cur = self._spotify.currently_playing()
            return cur['is_playing']
        except:
            return False


    def play(self, uris):
        """
        Set the list of URIs playing.
        """
        LOG.info("Playing: %s", ' '.join(uris))
        self._spotify.start_playback(uris     =uris,
                                     device_id=self._device_id)


    def pause(self):
        """
        Pause any currently playing music.
        """
        self._spotify.pause_playback(device_id=self._device_id)


    def unpause(self):
        """
        Resume any currently paused music.
        """
        self._spotify.start_playback(device_id=self._device_id)


    def _start(self):
        """
        @see Startable._start()
        """
        # This is what we need to be able to do
        scope = ','.join(('user-library-read',
                          'user-read-playback-state',
                          'user-modify-playback-state'))

        # Create the authorization manager, and then use that to create the
        # client
        auth_manager = SpotifyOAuth(client_id    =self._client_id,
                                    client_secret=self._client_secret,
                                    redirect_uri =self._redirect_uri,
                                    scope        =scope)
        self._spotify = Spotify(auth_manager=auth_manager)

        # See what devices we have to hand
        try:
            if self._device_name is not None:
                LOG.info("Looking for device named '%s'", self._device_name)

            devices = self._spotify.devices()
            for device in devices['devices']:
                # Say what we see
                name   = device['name']
                id_    = device['id']
                type_  = device['type']
                active = device['is_active']
                vol    = device['volume_percent']
                LOG.info("Found %sactive %s device: '%s'",
                         '' if active else 'in', type_, name)

                # See if we're looking for a specific device, if not just snoop
                # the volume from the first active one
                if self._device_name is not None:
                    if name == self._device_name:
                        LOG.info("Matched '%s' to ID '%s'", name, id_)
                        self._device_id = id_
                        self._volume    = vol / 100.0 * MAX_VOLUME
                else:
                    if active and self._volume is None:
                        self._volume = vol / 100.0 * MAX_VOLUME

        except Exception as e:
            LOG.warning("Unable to determine active Spoify devices: %s", e)

        # If we were looking for a specific device then make sure that we found
        # it in the list
        if self._device_name is not None and self._device_id is None:
            raise ValueError("Failed to find device with name '%s'" %
                             (self._device_name,))


    def _stop(self):
        """
        @see Startable._stop()
        """
        try:
            self._spotify.pause_playback(device_id=self._device_id)
        except:
            # Best effort
            pass


    def _match_artist(self, artist):
        """
        @see MusicService._match_artist()
        """
        artist = ' '.join(artist).lower()
        LOG.debug("Matching artist '%s'", artist)
        result = self._spotify.search(artist, type='artist')
        if 'artists' in result and 'items' in result['artists']:
            items = result['artists']['items']
            LOG.debug("Checking %d results", len(items))
            for item in items:
                name = item.get('name', '').lower()
                LOG.debug("Matching against '%s'", name)
                if fuzz.ratio(name, artist) > self._match_threshold:
                    return True
        return False


    def _get_stop_handler(self, tokens):
        """
        @see MusicService._get_stop_handler()
        """
        return _SpotifyServicePauseHandler(self, tokens)


    def _get_play_handler(self, tokens):
        """
        @see MusicService._get_play_handler()
        """
        return _SpotifyServiceUnpauseHandler(self, tokens)


    def _get_toggle_pause_handler(self, tokens):
        """
        @see MusicService._get_toggle_pause_handler()
        """
        return _SpotifyServiceTogglePauseHandler(self, tokens)


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
        name = ' '.join(song_or_album).lower()
        if artist is None or len(artist) == 0:
            artist = None
        else:
            artist = ' '.join(artist).lower()

        # We will put all the track URIs in here
        uris = []

        # Search by track name then album name, these are essentially the same
        # logic
        for which in ('track', 'album'):
            # What we matched on
            matches = []
            for with_artist in (True, False):
                if with_artist:
                    if not artist:
                        continue
                    search = '%s by %s' % (name, artist)
                    LOG.info("Looking for '%s' by %s as a %s",
                             name, artist, which)
                else:
                    search = name
                    LOG.info("Looking for '%s' as a %s",
                             name, which)

                # This is the key in the results
                plural = which + 's'

                # Try using the song_or_album as the name
                result = self._spotify.search(search, type=which)
                if not result:
                    LOG.info("No results")
                    continue

                # Did we get back any tracks
                if plural not in result:
                    LOG.error("%s was not in result keys: %s",
                              plural, result.keys())
                    continue

                # We got some results back, let's assign scores to them all
                results = result[plural]
                for item in results.get('items', []):
                    # It must have a uri
                    if 'uri' not in item and item['uri']:
                        LOG.error("No URI in %s", item)

                    # Look at all the candidate entries
                    if 'name' in item:
                        # See if this is better than any existing match
                        name_score = fuzz.ratio(name, item['name'].lower())
                        LOG.debug("'%s' matches '%s' with score %d",
                                  item['name'], name, name_score)

                        # Check to make sure that we have an artist match as well
                        if artist is None:
                            # Treat as a wildcard
                            artist_score = 100
                        else:
                            artist_score = 0
                            for entry in item.get('artists', []):
                                score = fuzz.ratio(artist, entry.get('name','').lower())
                                LOG.debug("Artist match score for '%s' was %d",
                                          entry.get('name',''), score)
                                if score > artist_score:
                                    artist_score = score
                        LOG.debug("Artist match score was %d", artist_score)

                        # Only consider cases where the scores look "good enough"
                        if name_score > self._match_threshold and \
                           artist_score > self._match_threshold:
                            LOG.info(
                                "Adding match of %s by %s "
                                "with name score %d and album score %d",
                                item['name'],
                                ' '.join(e.get('name', 'unknown artist')
                                         for e in item.get(
                                                 'artists',
                                                 [{'name' : 'unknown artist'}]
                                         )),
                                name_score,
                                artist_score
                            )
                            matches.append((item, name_score, artist_score))

            # Anything?
            if len(matches) > 0:
                LOG.debug("Got %d matches", len(matches))

                # Order them accordingly
                matches.sort(key=lambda e: (e[1], e[2]))

                # Now, pick the top one
                best = matches[0]
                item = best[0]
                LOG.debug("Best match was: %s", item)

                # Extract the info
                item_name = item.get('name', None) or name
                artists = item.get('artists', [])
                artist_name = (artists[0].get('name', None)
                               if len(artists) > 0 else None) or artist

                # Description of what we are playing
                what = item_name if item_name else name
                if artist_name:
                    what += " by " + artist_name
                what += " on Spotify"

                # The score is the geometric value of the two
                score = sqrt(best[1] * best[1] + best[2] * best[2]) / 100.0

                # The should be here
                assert 'uri' in item, "Missing URI in %s" % (item,)
                uri = item['uri']

                # If we are an album then grab the track URIs
                if which == 'album':
                    tracks = self._spotify.album_tracks(uri)
                    if tracks and 'items' in tracks:
                        uris = [track['uri'] for track in tracks['items']]
                else:
                    # Just the track
                    uris = [uri]

                # And we're done
                break

        # Otherwise assume that it's an artist
        if len(uris) == 0 and artist is None:
            LOG.info("Looking for '%s' as an artist", name)
            result = self._spotify.search(name, type='artist')
            LOG.debug("Got: %s", result)

            if result and 'artists' in result and 'items' in result['artists']:
                items = sorted(result['artists']['items'],
                               key=lambda entry: fuzz.ratio(
                                                     name,
                                                     entry.get('name', '').lower()
                                                 ),
                               reverse=True)

                # Look at the best one, if any
                LOG.debug("Got %d matches", len(items))
                if len(items) > 0:
                    match = items[0]
                    who   = match['name']
                    what = "%s on Spotify" % (who,)
                    score = fuzz.ratio(who.lower(), name)

                    # Find all their albums
                    if 'uri' in match:
                        LOG.debug("Got match: %s", match['uri'])
                        artist_albums = self._spotify.artist_albums(match['uri'])
                        for album in artist_albums.get('items', []):
                            # Append all the tracks
                            LOG.debug("Looking at album: %s", album)
                            if 'uri' in album:
                                tracks = self._spotify.album_tracks(album['uri'])
                                if tracks and 'items' in tracks:
                                    LOG.debug("Adding tracks: %s",
                                              ' '.join(track['name']
                                                       for track in tracks['items']))
                                    uris.extend([track['uri']
                                                 for track in tracks['items']])

        # And now we can give it back, if we had something, otherwise we say we
        # didn't match
        if len(uris) > 0:
            # We have something to play
            return _SpotifyServicePlayHandler(
                self,
                tokens,
                what,
                uris,
                score
            )
        else:
            # Build up what we were asked to play
            if genre is not None:
                what = '%s music' % genre
            else:
                what = ' '.join(song_or_album)
                if artist is not None:
                    what += ' by %s' % artist
            return _SpotifyServiceNoMatchHandler(
                self,
                tokens,
                what
            )
