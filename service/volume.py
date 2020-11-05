"""
Set the audio output volume. It goes up to 11.
"""

from   dexter.core.audio import MIN_VOLUME, MAX_VOLUME, get_volume, set_volume
from   dexter.core.log   import LOG
from   dexter.core.util  import fuzzy_list_range, parse_number
from   dexter.service    import Service, Handler, Result
from   fuzzywuzzy        import fuzz

import traceback

class _SetHandler(Handler):
    """
    Set the volume to a specific value.
    """
    def __init__(self, service, tokens, volume):
        """
        @see Handler.__init__()
        """
        super(_SetHandler, self).__init__(service, tokens, 1.0, True)
        self._volume = volume


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            value = parse_number(self._volume)
            LOG.info("Got value of %s from %s" % (value, self._volume))

            if value < MIN_VOLUME or value > MAX_VOLUME:
                # Bad value
                return Result(
                    self,
                    "Sorry, volume needs to be between %d and %d" %
                    (MIN_VOLUME, MAX_VOLUME),
                    False,
                    True
                )
            else:
                # Acknowledge that it happened
                set_volume(value)
                return Result(
                    self,
                    "Okay, volume now %s" % (value,),
                    False,
                    True
                )

        except Exception:
            LOG.error("Problem parsing volume '%s':\n%s" %
                      (self._volume, traceback.format_exc()))
            return Result(
                self,
                "Sorry, I don't know how to set the volume to %s" %
                (self._volume,),
                False,
                True
            )


class _AdjustHandler(Handler):
    """
    Raise or lower the volume by a delta.
    """
    def __init__(self, service, tokens, delta):
        """
        @see Handler.__init__()
        """
        super(_AdjustHandler, self).__init__(service, tokens, 1.0, True)
        self._delta = delta


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            # Make the change, capping at min and max
            cur = get_volume()
            new = max(MIN_VOLUME, min(MAX_VOLUME, cur + self._delta))

            # Any change?
            if cur != new:
                # Acknowledge that it happened
                set_volume(new)
                direction = "Up" if self._delta > 0 else "Down"
                return Result(self, direction, False, True)
            else:
                # Nothing to do
                return None

        except Exception:
            LOG.error("Problem setting changing the volume by %s:\n%s" %
                      (self._delta, traceback.format_exc()))
            return Result(
                self,
                "Sorry, there was a problem changing the volume",
                False,
                True
            )


class VolumeService(Service):
    """
    A service for setting the volume.
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(VolumeService, self).__init__("Volume", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        words = self._words(tokens)

        # Look for a direct setting
        prefix = ('set', 'volume', 'to')
        try:
            (start, end, _) = fuzzy_list_range(words, prefix)
            return _SetHandler(self, tokens, ' '.join(words[end:]))
        except:
            # Didn't find a match
            pass

        # For the below we need to up the threshold since:
        #  fuzz.ratio('turn up the volume','turn down the volume') == 84

        # Or a request to raise...
        for prefix in (('raise', 'the', 'volume'),
                       ('raise', 'volume'),
                       ('turn', 'the', 'volume', 'up'),
                       ('turn', 'up', 'the', 'volume')):
            try:
                (start, end, _) = fuzzy_list_range(words, prefix, threshold=85)
                if start == 0 and end == len(words):
                    return _AdjustHandler(self, tokens, 1)
            except:
                # Didn't find a match
                pass

        # ...or lower the volume
        for prefix in (('lower', 'the', 'volume'),
                       ('lower', 'volume'),
                       ('turn', 'the', 'volume', 'down'),
                       ('turn', 'down', 'the', 'volume')):
            try:
                (start, end, _) = fuzzy_list_range(words, prefix, threshold=85)
                if start == 0 and end == len(words):
                    return _AdjustHandler(self, tokens, -1)
            except:
                # Didn't find a match
                pass
            
        # Or to shut up completely
        for phrase in ('mute',
                       'silence',
                       'quiet',
                       'shut up'):
            if fuzz.ratio(' '.join(words), phrase) > 80:
                return _SetHandler(self, tokens, 'zero')

        # Otherwise this was not for us
        return None


