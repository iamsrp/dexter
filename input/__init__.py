"""
How Dexter gets instructions from outside world.

This might be via speech recognition, a network connection, etc.
"""

from dexter.core  import Component

# ------------------------------------------------------------------------------

class Token(object):
    """
    Part of the input.
    """
    def __init__(self, element, probability, verbal):
        """
        @type  element: str
        @param element:
            The thing which this token contains. This may be a word or it might
            be something like "<silence>". This depends on the input mechanism.
        @type  probability: float
        @param probability:
            The probability associated with this token.
        @type  verbal: bool
        @param verbal:
            Whether the token is a verbal one, or else a semantic one (like
            "<silence>").
        """
        self._element     = element
        self._probability = probability
        self._verbal      = verbal


    @property
    def element(self):
        return self._element


    @property
    def probability(self):
        return self._probability


    @property
    def verbal(self):
        return self._verbal


    def __str__(self):
        if self._verbal:
            return "\"%s\"(%0.2f)" % (self._element, self._probability)
        else:
            return "[%s](%0.2f)" % (self._element, self._probability)


class Input(Component):
    """
    A way to get text from the outside world.
    """
    def __init__(self, state):
        """
        @see Component.__init__()
        """
        super(Input, self).__init__(state)


    @property
    def is_input(self):
        """
        Whether this component is an input.
        """
        return True


    def read(self):
        """
        A non-blocking call to get a list of C{element}s from the outside world.

        Each C{element} is either a L{str} representing a word or a L{Token}.
        
        @rtype: tuple(C{element})
        @return:
            The list of elements received from the outside world, or None if
            nothing was available.
        """
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")
