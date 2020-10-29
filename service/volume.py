"""
Set the audio output volume. It goes up to 11.
"""

import traceback

from dexter.core.audio import set_volume
from dexter.core.log   import LOG
from dexter.core.util  import fuzzy_list_range, parse_number
from dexter.service    import Service, Handler, Result

class _Handler(Handler):
    def __init__(self, service, tokens, volume):
        """
        @see Handler.__init__()
        """
        super(_Handler, self).__init__(service, tokens, 1.0, True)
        self._volume = volume


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            value = parse_number(self._volume)
            LOG.info("Got value of %s from %s" % (value, self._volume))

            if value < 0 or value > 11:
                # Bad value
                return Result(
                    self,
                    "Sorry, volume needs to be between zero and eleven",
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
        words  = self._words(tokens)
        prefix = ('set', 'volume', 'to')
        try:
            (start, end, _) = fuzzy_list_range(words, prefix)
            return _Handler(self, tokens, ' '.join(words[end:]))
        except:
            # Didn't find a match
            return None

