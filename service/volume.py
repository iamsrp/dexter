'''
Set the audio output volume. It goes up to 11.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from dexter.core.audio import set_volume
from dexter.core.log   import LOG
from dexter.core.util  import list_index, parse_number
from dexter.service    import Service, Handler, Result

class _Handler(Handler):
    def __init__(self, service, tokens, volume):
        '''
        @see Handler.__init__()
        '''
        super(_Handler, self).__init__(service, tokens, 1.0, True)
        self._volume = volume


    def handle(self):
        '''
        @see Handler.handle()
        '''
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

        except Exception as e:
            LOG.error("Problem parsing volume '%s': %s" % (self._volume, e))
            return Result(
                self,
                "Sorry, I don't know how to set the volume to %s" %
                (self._volume,),
                False,
                True
            )


class VolumeService(Service):
    '''
    A service which simply parrots back what was given to it.
    '''
    def __init__(self, state):
        '''
        @see Service.__init__()
        '''
        super(VolumeService, self).__init__("Volume", state)


    def evaluate(self, tokens):
        '''
        @see Service.evaluate()
        '''
        # We use a number of different prefices here since the word "to" has a
        # bunch of homonyms and "set" apparently sounds like "said"...
        words    = self._words(tokens)
        prefices = (('set',  'volume', 'to' ),
                    ('set',  'volume', 'two'),
                    ('set',  'volume', 'too'),
                    ('said', 'volume', 'to' ),
                    ('said', 'volume', 'two'),
                    ('said', 'volume', 'too'),)
        for prefix in prefices:
            try:
                index = list_index(words, prefix)
                return _Handler(self,
                                tokens,
                                ' '.join(words[index + len(prefix):]))
            except:
                pass

        # Didn't find any of the prefices
        return None

