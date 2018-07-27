'''
How Dexter gets instructions from outside world.

This might be via speech recognition, a network connection, etc.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

# ------------------------------------------------------------------------------

class Token(object):
    '''
    Part of the input.
    '''
    def __init__(self, element, probability, verbal):
        '''
        '''
        self._element     = element
        self._probability = description
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


class Input(object):
    '''
    A way to get text from the outside world.
    '''
    def start(self):
        '''
        Start this input going.
        '''
        pass


    def stop(self):
        '''
        Stop this input.
        '''
        pass


    def read(self):
        '''
        A blocking call to get a list of C{element}s from the outside world. This
        will wait until a block of input has been received.

        Each C{element} is either a L{str} representing a word or a L{Token}.
        
        @rtype: tuple(C{element})
        @return:
            The list of elements received from the outside world.
        '''
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


    
