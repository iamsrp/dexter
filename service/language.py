"""
Services related to natural language.
"""

from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range
from   dexter.service   import Service, Handler, Result
from   math             import sqrt
from   PyDictionary     import PyDictionary

# ----------------------------------------------------------------------

class _DictionaryHandler(Handler):
    """
    The handler for the dictionary query.
    """
    def __init__(self, service, tokens, belief, word, limit):
        """
        @see Handler.__init__()

        :type  word: str
        :param word:
            The single word to look up.
        """
        super(_DictionaryHandler, self).__init__(service, tokens, belief, True)
        self._word  = str(word)
        self._limit = limit


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            result = self.service.meaning(self._word)
        except:
            return Result(
                self,
                "Sorry, I don't know the word %s" % self._word,
                False,
                True
            )

        # The result will contain lists keyed by word type
        response = "The word %s has the following definitions: " % self._word
        for type_ in result.keys():
            # Get back the list of definitlions, making it no more than the
            # given limit
            defns = result[type_][:self._limit]
            for defn in defns:
                # Make some tweaks to the definition
                defn = defn.lower()
                defn = defn.replace('e.g.', ' for example ')

                # And add it, along with its type
                response += "%s: %s. " % (type_, defn)

        # And give it all back
        return Result(self, response, False, True)


class DictionaryService(Service):
    """
    A service which looks up words in a  dictionary.
    """
    def __init__(self, state, limit=3):
        """
        @see Service.__init__()

        :type  limit: int
        :param limit:
            The limit results per word type (noun, verb, etc.).
        """
        super(DictionaryService, self).__init__("Dictionary", state)

        limit = int(limit)
        if limit < 0:
            raise ValueError("Bad limit value: %d" % limit)

        self._limit = limit
        self._dict  = PyDictionary()


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Get the words, ready to match with
        words = self._words(tokens)

        # This is how it could be phrased
        fixes = ((('define',),                            tuple()),
                 (('what', 'is', 'the', 'meaning', 'of'), tuple()),
                 (('what', 'does'),                       ('mean',)))
        match = None
        for (prefix, suffix) in fixes:
            try:
                # Look for the prefix and suffix in the words
                if len(prefix) > 0:
                    (pre_start, pre_end, pre_score) = fuzzy_list_range(words, prefix)
                else:
                    (pre_start, pre_end, pre_score) = (0, 0, 100)
                if len(suffix) > 0:
                    (suf_start, suf_end, suf_score) = fuzzy_list_range(words, suffix)
                else:
                    (suf_start, suf_end, suf_score) = (len(words), len(words), 100)
                LOG.debug("%s matches %s with from %d to %d with score %d, "
                          "and %s matches from %d to %d with score %d",
                          prefix, words, pre_start, pre_end, pre_score,
                          suffix,        suf_start, suf_end, suf_score)

                # We expect there to be only one word in the middle of the
                # prefix and suffix when we match
                if (pre_start   == 0          and
                    pre_end + 1 == suf_start  and
                    suf_end     == len(words) and
                    (match is None or match[2] < score)):
                    match = (pre_start, pre_end, pre_score,
                             suf_start, suf_end, suf_score)
            except ValueError:
                pass

        # Did we get anything?
        if match is not None:
            # Pull back the values
            (pre_start, pre_end, pre_score,
             suf_start, suf_end, suf_score) = match

            # The belief is the geometric distance of the scores
            belief = sqrt(pre_score * pre_score + suf_score * suf_score) / 100.0

            # The word is the one at pre_end (since it's non-inclusive)
            word = words[pre_end]

            # And give back the handler
            return _DictionaryHandler(self, tokens, belief, word, self._limit)
        else:
            # Nope, we got nothing
            return None


    def meaning(self, word):
        """
        Look up the meanings of the given word.
        """
        # Simple hand-off
        return self._dict.meaning(word)

# ----------------------------------------------------------------------

class _SpellingHandler(Handler):
    """
    The handler for the spelling query.
    """
    def __init__(self, service, tokens, belief, words):
        """
        @see Handler.__init__()

        :type  words: str
        :param words:
            The words to spell.
        """
        super(_SpellingHandler, self).__init__(service, tokens, belief, True)
        self._words = words


    def handle(self):
        """
        @see Handler.handle()
        """
        # Just join all the spellings together
        response = ""
        for word in self._words:
            # Strip trailing punctuation since that will be interpreted
            # incorrectly
            word = word.strip(',').strip('.')

            # User '.'s to slow down the rate at which the latters are spoken.
            response += "The word %s is spelt %s. " % (word, ' .'.join(word))

        # And give it all back
        return Result(self, response, False, True)


class SpellingService(Service):
    """
    A service which looks up words in a  spelling.
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(SpellingService, self).__init__("Spelling", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Get the words, ready to match with
        words = self._words(tokens)

        # Look for these prefixes
        prefices = (('spell',),
                    ('how', 'do', 'you', 'spell'))
        match = None
        for prefix in prefices:
            try:
                # Look for the prefix and suffix in the words
                (start, end, score) = fuzzy_list_range(words, prefix)
                LOG.debug("%s matches %s with from %d to %d with score %d",
                          prefix, words, start, end, score)

                # Get the best one
                if (start == 0 and (match is None or match[2] < score)):
                    match = (start, end, score)
            except ValueError:
                pass

        # Did we get anything?
        if match is not None:
            # Simply give these to the handler
            (start, end, score) = match
            return _SpellingHandler(self, tokens, score / 100.0, words[end:])
        else:
            # Nope, we got nothing
            return None
