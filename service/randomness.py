"""
Services which simulate random processes (coins, dice, etc.).
"""

from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range, parse_number
from   dexter.service   import Service, Handler, Result

import random

class _CoinTossHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, 1.0, True)


    def handle(self):
        """
        @see Handler.handle()
        """
        result = "heads" if random.randint(0, 1) else "tails"
        return Result(
            self,
            "You got %s" % result,
            False,
            True
        )


class _DiceHandler(Handler):
    def __init__(self, service, tokens, sides):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, 1.0, True)
        self._sides = sides


    def handle(self):
        """
        @see Handler.handle()
        """
        return Result(
            self,
            "You got a %d" % random.randint(1, self._sides),
            False,
            True
        )


class _RangeHandler(Handler):
    def __init__(self, service, tokens, start, end):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, 1.0, False)
        self._start = start
        self._end   = end


    def handle(self):
        """
        @see Handler.handle()
        """
        return Result(
            self,
            "%d" % random.randint(self._start, self._end),
            False,
            True
        )


class RandomService(Service):
    """
    A service which handles different types of random number requests.
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super().__init__("Random", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # The incoming request
        words = self._words(tokens)

        # Binary random number
        for phrase in ("toss a coin", "flip a coin"):
            try:
                fuzzy_list_range(words, phrase.split())
                return _CoinTossHandler(self, tokens)
            except ValueError:
                pass

        # A regular die
        for phrase in ("roll a die", "roll a dice"):
            try:
                fuzzy_list_range(words, phrase.split())
                return _DiceHandler(self, tokens, 6)
            except ValueError:
                pass
            
        # A generic request
        try:
            prefix = ('give', 'me', 'a', 'number', 'between')
            (_, offset, _)  = fuzzy_list_range(words, prefix)
            if len(words) >= offset + 3:
                and_index = words.index('and')
                start     = parse_number(words[offset     :and_index])
                end       = parse_number(words[and_index+1:])
                if start is not None and end is not None:
                    return _RangeHandler(self, tokens, start, end)
        except Exception as e:
            LOG.debug("Failed to handle '%s': %s" % (phrase, e))

        # Not for us
        return None
