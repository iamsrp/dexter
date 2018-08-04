'''
A simple service which echoes back the input,
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from dexter.service import Service, Handler, Result

class _EchoHandler(Handler):
    def __init__(self, service, tokens):
        '''
        @see Handler.__init__()
        '''
        super(_EchoHandler, self).__init__(service, tokens, 1.0, False)


    def handle(self):
        '''
        @see Handler.handle()
        '''
        return Result(
            self,
            "You said: %s" % ' '.join([token.element
                                       for token in self._tokens
                                       if token.verbal]),
            False,
            False
        )


class EchoService(Service):
    '''
    A service which simply parrots back what was given to it.
    '''
    def __init__(self, notifier):
        '''
        @see Service.__init__()
        '''
        super(EchoService, self).__init__("Echo", notifier)


    def evaluate(self, tokens):
        '''
        @see Service.evaluate()
        '''
        # We always handle these
        return _EchoHandler(self, tokens)

