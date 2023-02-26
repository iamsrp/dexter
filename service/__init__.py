"""
How we handle services (or applets) inside Dexter.

Each service provides something which responds to given input commands, and
possibly has some output too.
"""

from dexter.core  import Component
from dexter.input import Token

# ------------------------------------------------------------------------------

class Service(Component):
    """
    A service which responds to input.
    """
    def __init__(self, name, state):
        """
        :type  name: str
        :param name:
            The name of this service.
        :type  state: L{State}
        :param state:
            The global State instance.
        """
        super().__init__(state)
        self._name = name


    @property
    def is_service(self):
        """
        Whether this component is a service.
        """
        return True


    def evaluate(self, tokens):
        """
        Determine whether this service can handle the given C{tokens}. If the
        service believes that it can then it gives back a L{Handler}, else it
        returns C{None}.

        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        :rtype: L{Handler} or None
        :return:
             A L{Handler} for the given input tokens, or None.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def _words(self, tokens):
        """
        Get only the words from the tokens, all as lowercase.
        """
        return [token.element.lower()
                for token in tokens
                if token.verbal and token.element is not None]


class Handler(object):
    """
    A handler from a L{Service}. This corresponds to a particular set of input
    tokens.

    The belief of the handler is how well the service thinks it matched the
    query defined by the tokens. For example::
      User:     Hey Computer, what's the grime?
      Computer: The time is six forty eight PM.
    might result in a belief of 0.8 since only two thirds of the words were
    matched but the final word was _almost_ matched. If multiple handlers match
    a query string then the one with the highest belief is selected by the
    system..
    """
    def __init__(self, service, tokens, belief, exclusive):
        """
        :type  service: L{Service}
        :param service:
            The L{Service} instance which generated this L{Handler}.
        :type  tokens: tuple(L{Token})
        :param tokens:
            The tokens for which this handler was generated.
        :type  belief: float
        :param belief:
            How much the service believes that it can handle the given input. A
            value between 0 and 1.
        :type  exclusive: bool
        :param exclusive:
            Whether this handler should be the only one to be called.
        """
        super().__init__()
        self._service   = service
        self._tokens    = tokens
        self._belief    = belief
        self._exclusive = exclusive


    @property
    def service(self):
        return self._service


    @property
    def tokens(self):
        return self._tokens


    @property
    def belief(self):
        return self._belief


    @property
    def exclusive(self):
        return self._exclusive


    def handle(self):
        """
        Handle the input. This will be called on the main thread.

        :rtype: L{Result} or C{None}
        :return:
            The result of responding to the query, or None if no response.
        """
        # To be implemented by subclasses
        raise NotImplementedError("Abstract method called")


    def __str__(self):
        return "%s{%0.2f,%s}" % (self.service, self.belief, self.exclusive)


class Result(object):
    """
    The result of caling L{Handler.handle()}.

    This might be a simple response, for example::
      User:     Hey Computer, what's the capital of France.
      Computer: Paris.
    Or it might be something which requires more input from the user::
      User:     Hey Computer, tell me a joke.
      Computer: Knock, knock...
      ...

    Some results of a query might be considered canonical for a particular
    service. For example::
      User:    Hey Computer, play Captain Underpants by Weird Al.
      Computer: Okay, playing Captain Underpants Theme Song by Weird Al
                Yankovic.
    Here you would not want another service to also play Captain Underpants at
    the same time that the responding one does, once is plenty.
    """
    def __init__(self, handler, text, is_query, exclusive):
        """
        :type  handler: L{Handler}
        :param handler
            The L{Handler} instance which generated this L{Response}.
        :type  text: str
        :param text:
            The text of the response.
        :type  is_query: bool
        :param is_query:
            Whether or not this result is a query and expects the user to
            respond.
        :type  exclusive: bool
        :param exclusive:
            Whether this response should prevent the processing of any further
            ones.
        """
        super().__init__()
        self._handler   = handler
        self._text      = text
        self._is_query  = is_query
        self._exclusive = exclusive


    @property
    def handler(self):
        return self._handler


    @property
    def text(self):
        return self._text


    @property
    def is_query(self):
        return self._is_query


    @property
    def exclusive(self):
        return self._exclusive
