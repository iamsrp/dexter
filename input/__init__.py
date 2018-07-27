'''
How Dexter gets instructions from outside world.

This might be via speech recognition, a network connection, etc.
'''

from __future__ import (absolute_import, division, print_function,
                        with_statement)

# ------------------------------------------------------------------------------

class Token(object):
    '''
    A non-verbal part of the input.
    '''
    def __init__(self, token, description):
        '''
        '''
        self._token = token
        self._desc  = description


    @property
    def description(self):
        return self._desc


    def __str__(self):
        return '[%s]' % (self._token,)


class Input(object):
    '''
    A way to get text from the outside world.
    '''
    PAUSE = Token("pause", "A pause in then spoken input")

    def __init__(self):
        '''
        CTOR
        '''
        super(Input, self).__init__()


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


    
