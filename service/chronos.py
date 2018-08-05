'''
Chronos, the greek god of Thyme, and other select herbs.

Various services related to the ticking of the clock.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import time

from   dexter.core.util import to_letters
from   dexter.service   import Service, Handler, Result

# ------------------------------------------------------------------------------

class _ClockHandler(Handler):
    def __init__(self, service, tokens):
        '''
        @see Handler.__init__()
        '''
        super(_ClockHandler, self).__init__(service, tokens, 1.0, True)


    def handle(self):
        '''
        @see Handler.handle()
        '''
        # Get the time in the local timezone and render the component parts that
        # we care about. We strip leading zeroes, which you expect for a HH:MM
        # format, so that it doesn't confuse the speech output.
        now = time.localtime(time.time())
        hh  = time.strftime("%I", now).lstrip('0')
        mm  = time.strftime("%M", now).lstrip('0')
        p   = time.strftime("%p", now)

        # Now we can hand it back
        return Result(
            self,
            "The current time is %s %s %s" % (hh, mm, p),
            False,
            True
        )


class ClockService(Service):
    '''
    A service which tells the time.

    >>> from dexter.test import NOTIFIER, tokenise
    >>> s = ClockService(NOTIFIER)
    >>> handler = s.evaluate(tokenise('What\\'s the time?'))
    >>> result = handler.handle()
    >>> result.text.startswith('The current time is')
    True
    '''
    def __init__(self, notifier):
        '''
        @see Service.__init__()
        '''
        super(ClockService, self).__init__("Clock", notifier)


    def evaluate(self, tokens):
        '''
        @see Service.evaluate()
        '''
        # Get stripped text, for matching
        text = ' '.join(to_letters(w) for w in self._words(tokens))

        # See if it matches an expected string
        for want in ('whats the time',
                     'what is the time'):
            if text == want:
                return _ClockHandler(self, tokens)

        # If we got here, then we didn't get an exact match
        return None

# ------------------------------------------------------------------------------

