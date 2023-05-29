"""
A way to index media.
"""

from   dexter.core.log import LOG
from   fuzzywuzzy      import process
from   threading       import Lock

import math
import mutagen
import os
import time

# ------------------------------------------------------------------------------

class MusicIndex:
    """
    Index music in various ways.
    """
    def __init__(self):
        # The various indices. These are of the form <str,tuple(_Entry)>.
        self._by_name   = {}
        self._by_artist = {}
        self._by_album  = {}
        self._count     = 0
        self._lock      = Lock()


    def lookup(self, name=None, artist=None, album=None):
        """
        Look up an entry by any given constraints.

        :type  name: str
        :param name:
            The name of the track.
        :type  artist: str
        :param artist:
            The artist of the track.
        :type  album: str
        :param album:
            The album the track is from.

        :rtype: tuple<Entry>
        :return:
           The potential entries, in order of likely match. Possibly empty.
        """
        # Look in all our indices. We will create lists of (Entry,score) pairs
        # for each. We do this under the lock so that nothing changes in the
        # dicts.
        with self._lock:
            if name is not None and len(self._by_name) > 0:
                key, score = process.extractOne(name, self._by_name.keys())
                by_name    = [(entry, score) for entry in self._by_name[key]]
            else:
                by_name = None

            if artist is not None and len(self._by_artist) > 0:
                key, score = process.extractOne(artist, self._by_artist.keys())
                by_artist  = [(entry, score) for entry in self._by_artist[key]]
            else:
                by_artist = None

            if album is not None and len(self._by_album) > 0:
                key, score = process.extractOne(album, self._by_album.keys())
                by_album   = [(entry, score) for entry in self._by_album[key]]
            else:
                by_album = None

        # Now combine the results by intersecting all the matches
        results = None
        for matches in (by_name, by_album, by_artist):
            if results is None:
                results = matches
            elif matches is not None:
                new = []
                for match in matches:
                    for result in results:
                        if match[0] is result[0]:
                            new.append(
                                (match[0], math.sqrt(match [1] * match [1] +
                                                     result[1] * result[1]))
                            )
                results = new

        # And give them back
        if results is None:
            return tuple()
        else:
            return tuple(
                result[0]
                for result in sorted(results, key=lambda e: e[1], reverse=True)
            )


    def _add_entry(self, entry):
        """
        Add an entry to the index.

        :type  entry: _Entry
        :param entry:
            The entry to add to the index.
        """
        # Ignore entries with no name
        if entry.name is None:
            return
        LOG.debug("Adding '%s'", entry.name if entry.name else entry.url)

        # Sanitise the strings thusly. This attempts to do a little data
        # cleaning along the way.
        def tidy(string):
            # Deal with empty strings
            string = _clean_string(string)
            if string is None:
                return None

            # Handle "_"s instead of spaces
            string = string.replace('_', ' ')
            string = _clean_string(string)
            if string is None:
                return None

            # Put ", The" back on the front
            if string.endswith(' The'):
                if string.endswith(', The'):
                    string = "The " + string[:-5]
                else:
                    string = "The " + string[:-4]

            # And, finally, make it all lower case so that we don't get fooled
            # by funny capitalisation
            string = string.lower()

            # And give it back
            return string.lower()

        # How we add the entry to an index
        def add(key, index, entry_):
            if key is not None:
                if key in index:
                    index[key].append(entry_)
                else:
                    index[key] = [entry_]

        # Add to the various indices. We do this under the lock so that readers
        # are not confused.
        with self._lock:
            add(tidy(entry.name  ), self._by_name,   entry)
            add(tidy(entry.artist), self._by_artist, entry)
            add(tidy(entry.album ), self._by_album,  entry)

        # And update the stats
        self._count += 1
        if (self._count % 1000) == 0:
            LOG.info("Added a total of %d entries...", self._count)


    def __len__(self):
        return self._count


class FileMusicIndex(MusicIndex):
    """
    Index music from a filesystem.
    """
    def __init__(self, roots):
        """
        :type  roots: tuple(str)
        :param roots:
            The list of URLs to search for music on. In the simplest form these
            will likely just be a bunch of strings looking something like:
                C{file:///home/pi/Music}
        """
        super().__init__()

        # Tupleize, just in case someone passed in a string or whathaveyou
        if isinstance(roots, str):
            roots = (roots,)
        elif not isinstance(roots, (tuple, list)):
            roots = tuple(roots)

        if roots is not None:
            for root in roots:
                start = time.time()
                self._build(root)
                end  = time.time()
                LOG.info("Indexed %s in %0.1f seconds", root, end - start)


    def _build(self, root):
        """
        Build an index based on the given root.

        :type  root: str
        :param root:
            The URL of the root to build from.
        """
        if root is None:
            return
        if not isinstance(root, str):
            raise ValueError("Root was not a string: %r", root)
        if root.startswith('file://'):
            self._build_file(root[len('file://'):])
        elif root.startswith('/'):
            self._build_from_dirname(root)
        else:
            raise ValueError("Unhandled root type: %s", root)


    def _build_from_dirname(self, dirname):
        """
        Build an index based on the given directory root.

        :type  dirname: str
        :param dirname:
            The directory name to build from.
        """
        # Walk the tree
        for (subdir, subdirs, files) in os.walk(dirname, followlinks=True):
            LOG.info("Indexing %s", subdir)

            # Handle all the files which we can find
            for filename in files:
                try:
                    # Use mutagen to grab details
                    path = os.path.join(subdir, filename)
                    info = mutagen.File(path)
                    if isinstance(info, mutagen.mp3.MP3):
                        self._add_entry(AudioEntry.from_mp3(info))
                    elif isinstance(info, mutagen.flac.FLAC):
                        self._add_entry(AudioEntry.from_flac(info))
                    else:
                        LOG.debug("Ignoring %s", path)
                except Exception as e:
                    LOG.warning("Failed to index %s: %s", path, e)



class _Entry:
    """
    An entry in the media index. This contains all the details which you need to
    know about a particular piece of media.
    """
    # The types of file which we know about
    MP3    = 'mp3'
    FLAC   = 'flac'
    STREAM = 'stream'


    def __init__(self, name, url, file_type):
        """
        :type  name: str
        :param name:
            The name of this piece of media.
        :type  url: str, or None
        :param url:
            The URL to access this piece of media, if any.
        :type  file_type: str
        :param file_type:
            The type of file.
        """
        self._name = _clean_string(name)
        self._url  = _clean_string(url)
        self._type = file_type


    @property
    def name(self):
        """
        The name of the entry. An audio track title, for example.

        :rtype: str
        :return:
            The name of the entry.
        """
        return self._name


    @property
    def url(self):
        """
        The URL to access this entry, if any.

        :rtype: str
        :return:
            The URL for the entry.
        """
        return self._url


    @property
    def file_type(self):
        """
        The type of data.

        :rtype: str
        :return:
            The type of data which we hold.
        """
        return self._type


    def __str__(self):
        if self.url and len(self.url) > 80:
            url = self.url[:80] + "..."
        else:
            url = self.url
        return f'{self.name}<{self.file_type}|{url}>'


class AudioEntry(_Entry):
    """
    An entry for an audio file, like MP3 or Flac.
    """
    @staticmethod
    def from_mp3(info):
        """
        Factory method to create an entry from MP3 data.

        :type  info: mutagen.mp3.MP3
        :param info:
            The mp3 tag information.
        """
        # Sanity
        if info is None:
            return None

        # Defaults
        name   = None
        url    = 'file://%s' % _clean_filename(info.filename)
        track  = None
        album  = None
        artist = None

        # Look for values
        for (key, value) in info.items():
            if   key == 'TALB':
                album = value.text[0]
            elif key == 'TIT2':
                name = value.text[0]
            elif key == 'TPE1':
                artist = value.text[0]
            elif key == 'TRCK':
                track = value.text[0]

        # Any name?
        if name is None:
            _, name = os.path.split(filename)
            if name.endswith('.mp3'):
                name = name[:-4]

        # And construct
        return AudioEntry(name, url, _Entry.MP3, track, album, artist)


    @staticmethod
    def from_flac(info):
        """
        Factory method to create an entry from FLAC data.

        :type  info: mutagen.flac.FLAC
        :param info:
            The flac tag information.
        """
        # Sanity
        if info is None:
            return None

        # Defaults
        name   = None
        url    = 'file://%s' % _clean_filename(info.filename)
        track  = None
        album  = None
        artist = None

        # Look for values
        for (key, value) in info.items():
            if   key == 'album':
                album = value[0]
            elif key == 'title':
                name = value[0]
            elif key == 'artist':
                artist = value[0]
            elif key == 'tracknumber':
                track = value[0]

        # Any name?
        if name is None:
            _, name = os.path.split(filename)
            if name.endswith('.flac'):
                name = name[:-4]

        # And construct
        return AudioEntry(name, url, _Entry.FLAC, track, album, artist)


    @staticmethod
    def from_music_track(track):
        """
        Factory method to create an entry from a DLNA MusicTrack object.

        :type  track: didl_lite.didl_lite.MusicTrack
        :param track:
            The MusicTrack object..
        """
        # Sanity
        if track is None:
            return None

        # Get the URL. We must have this or we can't do anything.
        url = None
        for res in getattr(track, 'res', []):
            uri = getattr(res, 'uri', None)
            if uri and uri.startswith('http'):
                url = uri
                break
        if not url:
            return None

        # Pull out the info
        name   = (getattr(track, 'title',                 '') or '').strip() or None
        track  = (getattr(track, 'original_track_number', '') or '').strip() or None
        album  = (getattr(track, 'album',                 '') or '').strip() or None
        artist = (getattr(track, 'artist',                '') or '').strip() or None

        # We need a name too
        if not name:
            return

        # And construct
        return AudioEntry(name, url, _Entry.STREAM, track, album, artist)


    def __init__(self, name, url, file_type, track, album, artist):
        """
        @see _Entry.__init__()

        :type  name: str
        :param name:
            The name of the track.
        :type  track: interpretable as int, or None
        :param track:
            The track number, if any
        :type  album: str, or None
        :param album:
            The name of the album, of any.
        :type  artist: str, or None
        :param artist:
            The name of the artist, if any
        """
        super().__init__(name, url, file_type)
        self._track  = _clean_int   (track)
        self._album  = _clean_string(album)
        self._artist = _clean_string(artist)


    @property
    def track(self):
        """
        The track number of this entry, if any.

        :rtype: int, or None
        :return:
            The track index.
        """
        return self._track


    @property
    def album(self):
        """
        The album name for this entry, if any.

        :rtype: str
        :return:
            The album name.
        """
        return self._album


    @property
    def artist(self):
        """
        The artist for this entry, if any. This may typically be the performer but
        might also be the composer.

        :rtype: str
        :return:
            The artist name.
        """
        return self._artist

# ------------------------------------------------------------------------------

def _clean_string(string):
    """
    Turn empty strings into None and remove surrounding whitespace.

    :type  string: str
    :param string:
        The string to clean.

    :rtype: str
    :return:
       The cleaned string, or None.
    """
    if string is None:
        return None

    # Remove whitespace
    string = string.strip()

    if len(string) == 0:
        return None

    return string


def _clean_int(integer):
    """
    Turn a value into an integer, taking strings and yielding None where
    appropriate.

    :type  integer: int
    :param integer:
        The string to clean.

    :rtype: int
    :return:
       The cleaned int, or None.
    """
    if isinstance(integer, int):
        return integer

    integer = _clean_string(integer)
    if integer is None:
        return None

    try:
        return int(integer)
    except:
        return None


def _clean_filename(filename):
    """
    Ensure that a filename is good for our purposes.

    :type  filename: str
    :param filename:
        The filename to clean.

    :rtype: str
    :return:
       The cleaned filename, or None.
    """
    filename = _clean_string(filename)
    if filename is None:
        return None

    # It needs to be absolute, since we will use it in a URL
    if not filename.startswith('/'):
        filename = os.path.abspath(filename)

    return filename
