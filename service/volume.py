'''
Set the audio output volume. It goes up to 11.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from dexter.core      import LOG
from dexter.core.util import list_index, parse_number, set_volume
from dexter.service   import Service, Handler, Result

class _VolumeHandler(Handler):
    def __init__(self, service, tokens, volume):
        '''
        @see Handler.__init__()
        '''
        super(_VolumeHandler, self).__init__(service, tokens, 1.0)
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
                # No text, just do it
                set_volume(value)
                return Result(
                    self,
                    None,
                    False,
                    True
                )
        except Exception as e:
            LOG.error("Problem parsing volume '%s': %s" % (self._volume, e))
            return Result(
                self,
                "Sorry, I don't know how to set the volume to %s" %
                (' '.join(self._volume),),
                False,
                True
            )


class VolumeService(Service):
    '''
    A service which simply parrots back what was given to it.
    '''
    def __init__(self, notifier):
        '''
        @see Service.__init__()
        '''
        super(VolumeService, self).__init__("Volume", notifier)


    def evaluate(self, tokens):
        '''
        @see Service.evaluate()
        '''
        try:
            prefix = ['set', 'volume', 'to']
            words  = [token.element.lower()
                      for token in tokens
                      if token.verbal and token.element is not None]
            index  = list_index(words, prefix)

            return _VolumeHandler(self,
                                  tokens,
                                  ' '.join(words[index + len(prefix):]))
        except:
            return None

