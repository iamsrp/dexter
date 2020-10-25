"""
Chronos, the greek god of Thyme, and other select herbs.

Various services related to the ticking of the clock.
"""

import time

from   dexter.core.log  import LOG
from   dexter.core.util import to_letters, number_to_words
from   dexter.service   import Service, Handler, Result

# ------------------------------------------------------------------------------

class _ClockHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_ClockHandler, self).__init__(service, tokens, 1.0, True)


    def handle(self):
        """
        @see Handler.handle()
        """
        # Get the time in the local timezone and render the component parts that
        # we care about
        now = time.localtime(time.time())
        hh  = time.strftime("%I", now)
        mm  = time.strftime("%M", now)
        p   = time.strftime("%p", now)

        # We strip any leading zero from the HH, which you expect for a HH:MM
        # format. For MM we replace it with 'oh' for a more natural response.
        if hh.startswith('0'):
            hh = hh.lstrip('0')
        hh = number_to_words(int(hh))
        if mm == '00':
            mm = ''
        elif mm.startswith('0'):
            mm = 'oh %s' % number_to_words(int(mm))
        else:
            mm = number_to_words(int(mm))

        # Now we can hand it back
        return Result(
            self,
            "The current time is %s %s %s" % (hh, mm, p),
            False,
            True
        )


class ClockService(Service):
    """
    A service which tells the time.

    >>> from dexter.test import NOTIFIER, tokenise
    >>> s = ClockService(NOTIFIER)
    >>> handler = s.evaluate(tokenise('What\\'s the time?'))
    >>> result = handler.handle()
    >>> result.text.startswith('The current time is')
    True
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(ClockService, self).__init__("Clock", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Get stripped text, for matching
        text = ' '.join(to_letters(w) for w in self._words(tokens))

        # See if it matches an expected string
        for want in ('whats the time',
                     'what is the time',
                     'what time is it'):
            if text == want:
                LOG.info("Matched input on '%s'" % text)
                return _ClockHandler(self, tokens)

        # If we got here, then we didn't get an exact match
        return None

# ------------------------------------------------------------------------------

