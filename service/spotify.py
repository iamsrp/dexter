"""
A simple Spotify client, using ``spotipy`` under the hood.

This code is currently alpha quality and doesn't actually work yet.
"""

from   dexter.core.log          import LOG
from   dexter.core.util         import homonize, fuzzy_list_range
from   dexter.service           import Service, Handler, Result
from   fuzzywuzzy               import fuzz
from   math                     import sqrt
from   spotipy                  import Spotify
from   spotipy.oauth2           import SpotifyOAuth
from   threading                import Thread
from   .music                   import MusicService

# ------------------------------------------------------------------------------

class _SpotifyServicePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_SpotifyServicePauseHandler, self).__init__(
            service,
            tokens,
            1.0 if service.is_playing() else 0.0,
            False
        )


    def handle(self):
        """
        @see Handler.handle()`
        """
        was_playing = self.service.is_playing()
        self.service.pause()
        return Result(self, '', False, was_playing)


class _SpotifyServiceUnpauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_SpotifyServiceUnpauseHandler, self).__init__(
            service,
            tokens,
            1.0  if service.is_paused() else 0.0,
            True if service.is_paused() else False,
        )


    def handle(self):
        """
        @see Handler.handle()`
        """
        was_paused = self.service.is_paused()
        self.service.unpause()
        return Result(self, '', False, was_paused)


class _SpotifyServiceTogglePauseHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_SpotifyServiceTogglePauseHandler, self).__init__(
            service,
            tokens,
            1.0  if service.is_paused() or service.is_playing() else 0.0,
            True if service.is_paused() or service.is_playing() else False,
        )


    def handle(self):
        """
        @see Handler.handle()`
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
        super(_SpotifyServicePlayHandler, self).__init__(
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


class SpotifyService(MusicService):
    """
    Music service for local files.
    """
    def __init__(self, state, client_id=None, client_secret=None):
        """
        @see Service.__init__()

        :type  client_id: str
        :param client_id:
            The Spotify client ID.
        :type  client_secret: str
        :param client_secret:
            The Spotify client secret,
        """
        super(SpotifyService, self).__init__("SpotifyService",
                                             state,
                                             "Spotify")

        self._client_id     = client_id
        self._client_secret = client_secret
        self._spotify       = None
        self._volume        = None


    def start(self):
        """
        @see Startable.start()
        """
        # Create the client
        auth_manager = SpotifyOAuth(scope=(','.join(('user-library-read',
                                                     'user-read-playback-state',
                                                     'user-modify-playback-state'))))
        self._spotify = Spotify(auth_manager=auth_manager)


    def set_volume(self, volume):
        """
        @see MusicService.set_volume()
        """
        # Not supported, just record it
        self._volume = volume


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
        return self._spotify.currently_playing() is not None


    def play(self, uris):
        """
        Set the list of URIs playing.
        """
        LOG.error("Playing: %s", ' '.join(uris))
        self._spotify.start_playback(uris=uris)


    def pause(self):
        """
        Pause any currently playing music.
        """
        self._spotify.pause_playback()


    def unpause(self):
        """
        Resume any currently paused music.
        """
        self._spotify.start_playback()


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
                if fuzz.ratio(name, artist) > 80:
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
            LOG.info("Looking for '%s'%s as a %s",
                     name,
                     " by '%s'" % artist if artist else '',
                     which)

            # This is the key in the results
            plural = which + 's'

            # Try using the song_or_album as the name
            result = self._spotify.search(name, type=which)
            if not result:
                LOG.info("No results")
                continue

            # Did we get back any tracks
            if plural not in result:
                LOG.error("%s was not in result keys: %s", plural, result.keys())
                continue

            # We got some results back, let's assign scores to them all
            results = result[plural]
            matches = []
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
                    if name_score > 75 and artist_score > 75:
                        LOG.debug("Adding match")
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
        if len(uris) == 0:
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

        # And now we can give it back, if we had something
        if len(uris) > 0:
            return _SpotifyServicePlayHandler(
                self,
                tokens,
                what,
                uris,
                score
            )
        else:
            # We got nothing
            return None
