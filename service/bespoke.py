"""
A service which handles sets of stock phrases with specific replies. This is
where you should put all the humourous request/response stuff.
"""

from dexter.service   import Service, Handler, Result
from dexter.core.log  import LOG
from dexter.core.util import fuzzy_list_range, to_alphanumeric

# ----------------------------------------------------------------------

# A tuple of the form:
#   Phrase    -- What to match against
#   Reply     -- What to reply with
#   Is-Prefix -- Whether the Phrase was a prefix, or else a full one
# This should not contain anything "controversial", young ears may be listening.
_PHRASES = (
    ("Format c colon",
     "You'll have to do that for me; I cannot self-terminate.",
     False),
    ("Open pod bay doors",
     "i'm sorry dave, i can't do that.",
     True),
    ("What is the meaning of life?",
     "The answer is, of course, forty two.",
     False),
    ("Are you my friend?",
     "I am a simulated organism. Any feelings you may have are merely illusionary.",
     False),
    ("Do you like",
     "My ability to like or dislike is due in a future update.",
     True),
    ("Are you",
     "Since i am not self aware i am not sure i can answer that.",
     True),
    ("Plot a course for",
     "Course laid in. Speed, standard by twelve.",
     True),
    ("Have you seen my keys?",
     "I have not, where were you when you last had them?",
     False),
    ("Where are my keys?",
     "I don't know, where were you when you last had them?",
     False),
)


class _BespokeHandler(Handler):
    def __init__(self, service, tokens, reply):
        """
        @see Handler.__init__()

        :type reply: str
        :param reply:
            What to respond with.
        """
        super(_BespokeHandler, self).__init__(service, tokens, 1.0, True)
        self._reply = reply


    def handle(self):
        """
        @see Handler.handle()
        """
        return Result(self, self._reply, True, False)


class BespokeService(Service):
    """
    A service which simply parrots back what was given to it.
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(BespokeService, self).__init__("Bespoke", state)

        # Pre-process the stored data to get it into a form which is easier to
        # process in evaluate().
        self._phrases = tuple((tuple(to_alphanumeric(word)
                                     for word in phrase.split()),
                               reply,
                               is_prefix)
                              for (phrase, reply, is_prefix) in _PHRASES)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # The incoming text
        words = self._words(tokens)

        # Look for the match phrases
        for (phrase, reply, is_prefix) in self._phrases:
            try:
                LOG.debug("Looking for %s in %s", phrase, words)
                (start, end, score) = fuzzy_list_range(words, phrase)
                LOG.debug("Matched [%d:%d] and score %d", start, end, score)
                if start == 0 and (not is_prefix or end == len(phrase)):
                    return _BespokeHandler(self, tokens, reply)
            except ValueError as e:
                LOG.debug("No match: %s", e)
