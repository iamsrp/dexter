'''
How we handle services (or applets) inside Dexter.

Each service provides something which responds to given input commands, and
possibly has some output too.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from ..input import Token

# ------------------------------------------------------------------------------

class Handler(object):
    '''
    A handler from a L{Service}. This corresponds to a particular set of input
    tokens.
    '''
    def __init__(self, service, tokens, belief, exclusive):
        '''
        @type  service: L{Service}
        @param service:
            The L{Service} instance which generated this L{Handler}.
        @type  tokens: tuple(L{Token})
        @param tokens:
            The tokens for which this handler was generated.
        @type  belief: float
        @param belief:
            How much the service believes that it can handle the given input. A
            value between 0 and 1.
        @type  exclusive: bool
        @param exclusive:
            Whether the service believes that it should be the only handler for
            the input.
        '''
        super(Handler, self).__init__()
        self._service   = service
        self._tokens    = tokens
        self._belief    = belief
        self._exclusive = exclusive
        self._handler   = handler


    @property
    def service(self):
        return self._service


    @property
    def belief(self):
        return self._belief


    @property
    def exclusive(self):
        return self._exclusive


    def handle(self):
        '''
        Handle the input.

        @rtype: str or None
        @return:
            A string which will be passed to the system's outputs, or None if
            no response.
        '''
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


class Service(object):
    '''
    A service which responds to input.
    '''
    def __init__(self, name):
        '''
        @type  name: str
        @param name:
            The name of this service.
        '''
        super(Service, self).__init__()
        self._name = name


    def evaluate(self, tokens):
        '''
        Determine whether this service can handle the given C{tokens}. If the
        service believes that it can then it gives back a L{Handler}, else it
        returns C{None}.

        @type  tokens: tuple(L{Token})
        @param tokens:
            The tokens for which this handler was generated.
        @rtype: L{Handler} or None
        @return:
             A L{Handler} for the given input tokens, or None.
        '''
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")

