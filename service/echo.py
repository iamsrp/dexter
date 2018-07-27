


from __future__ import (absolute_import, division, print_function,
                        with_statement)

from . import Service, Handler

class _EchoHandler(Handler):
    def __init__(self, service, tokens):
        super(EchoService, self).__init__(service, tokens, 1.0, False)


    def handle(self):
        return "You said: %s" % [str(token) for token in self._tokens]


class EchoService(Service):
    '''
    A service which simply parrots back what was given to it.
    '''
    def __init__(self):
        super(EchoService, self).__init__("Echo")


    def evaluate(self, tokens):
        '''
        @see Service.evaluate()
        '''
        # We always handle these
        return _EchoHandler(self, tokens)

