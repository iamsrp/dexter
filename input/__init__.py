'''
How Dexter gets instructions from outside world.

This might be via speech recognition, a network connection, etc.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from dexter.core  import Component

# ------------------------------------------------------------------------------

class Token(object):
    '''
    Part of the input.
    '''
    def __init__(self, element, probability, verbal):
        '''
        '''
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
        string = "[%s](%0.2f)" % (self._element, self._probability)
        if self._non_verbal:
            return "[%s]" % string
        else:
            return string


class Input(Component):
    '''
    A way to get text from the outside world.
    '''
    def __init__(self):
        super(Input, self).__init__()


    def read(self):
        '''
        A non-blocking call to get a list of C{element}s from the outside world.

        Each C{element} is either a L{str} representing a word or a L{Token}.
        
        @rtype: tuple(C{element})
        @return:
            The list of elements received from the outside world, or None if
            nothing was available.
        '''
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")
