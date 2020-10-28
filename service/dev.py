"""
Services to aid with development and debugging.
"""

from dexter.service   import Service, Handler, Result
from dexter.core.util import fuzzy_list_range

# ----------------------------------------------------------------------

class _EchoHandler(Handler):
    def __init__(self, service, tokens):
        """
        @see Handler.__init__()
        """
        super(_EchoHandler, self).__init__(service, tokens, 1.0, False)


    def handle(self):
        """
        @see Handler.handle()
        """
        return Result(
            self,
            "You said: %s" % ' '.join([token.element
                                       for token in self._tokens
                                       if token.verbal]),
            False,
            False
        )


class EchoService(Service):
    """
    A service which simply parrots back what was given to it.
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(EchoService, self).__init__("Echo", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # We always handle these
        return _EchoHandler(self, tokens)

# ----------------------------------------------------------------------

class _MatchHandler(Handler):
    def __init__(self, service, tokens, matches, best):
        """
        @see Handler.__init__()
        """
        super(_MatchHandler, self).__init__(service, tokens, best / 100, False)
        self._matches = matches


    def handle(self):
        """
        @see Handler.handle()
        """
        result = list()
        for (phrase, words, (start, end, score)) in self._matches:
            result.append(
                "'%s' from [%d:%d] with '%s' scoring %d" % (
                    ' '.join(phrase), start, end, ' '.join(words), score
                )
            )

        return Result(
            self,
            "You matched: %s" % '; and '.join(result),
            False,
            False
        )


class MatchService(Service):
    """
    A service which attempts to do an approximate match on a set of word lists.
    """
    def __init__(self, state, phrases=[]):
        """
        @see Service.__init__()
        """
        super(MatchService, self).__init__("Match", state)

        self._phrases = tuple(
            tuple(
                w.strip()
                for w in phrase.strip().split()
                if w.strip()
            )
            for phrase in phrases
        )


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Look for a match in the phrases
        words   = self._words(tokens)
        matches = []
        best    = None
        for phrase in self._phrases:
            try:
                result = fuzzy_list_range(phrase, words)
                matches.append((phrase, words, result))
                (_, _, score) = result
                if best is None or best < score:
                    best = score
            except ValueError:
                pass
        if len(matches) > 0:
            return _MatchHandler(self, tokens, tuple(matches), best)
        else:
            return None

