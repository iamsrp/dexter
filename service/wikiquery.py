"""
Pull information from Wikipedia.
"""

from   dexter.core      import Notifier
from   dexter.core.log  import LOG
from   dexter.core.util import fuzzy_list_range
from   dexter.service   import Service, Handler, Result
from   fuzzywuzzy       import fuzz

import wikipedia


class _Handler(Handler):
    """
    The handler for Wikipedia queries.
    """
    def __init__(self, service, tokens, belief, thing):
        """
        @see Handler.__init__()

        :type  thing: str
        :param thing:
            What, or who, is being asked about.
        """
        super(_Handler, self).__init__(service, tokens, belief, False)
        self._thing = str(thing)


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            LOG.info("Querying Wikipedia for '%s'" % (self._thing,))
            summary = wikipedia.summary(self._thing, auto_suggest=False)
        except Exception as e:
            LOG.error("Failed to query Wikipedia about '%s': %s" %
                      (self._thing, e))
            return Result(
                self,
                "Sorry, there was a problem asking Wikipedia about %s" % (
                    self._thing,
                ),
                False,
                True
            )

        # Anything?
        if summary is None or len(summary.strip()) == 0:
            return None

        # Strip the summary down a little, some of these can be pretty
        # long. First just grab the first paragraph. Next, stop after about
        # 400 chars.
        shortened = summary.split('\n')[0]
        if len(shortened) > 400:
            # Skip doing this if we don't find a sentence end marker
            try:
                index = shortened.index('. ', 398)
                shortened = shortened[:index+1]
            except ValueError:
                pass

        # And give it back. We use a period after "says" here so that the speech
        # output will pause appropriately. It's not good gramma though. Since we
        # got back a result then we mark ourselves as exclusive; there is
        # probably not a lot of point in having others also return information.
        return Result(self,
                      "Wikipedia says.\n%s" % shortened,
                      False,
                      True)


class WikipediaService(Service):
    """
    A service which attempts to look for things on Wikipedia.

    >>> from dexter.test import NOTIFIER, tokenise
    >>> s = WikipediaService(NOTIFIER)
    >>> handler = s.evaluate(tokenise('who is mark shuttleworth'))
    >>> result = handler.handle()
    >>> result.text.startswith('Wikipedia says.\\nMark')
    True
    """
    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super(WikipediaService, self).__init__("Wikipedia", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Render to lower-case, for matching purposes.
        words = self._words(tokens)

        # Look for these types of queston
        prefices = (('what', 'is', 'a'),
                    ('what', 'is', 'the'),
                    ('what', 'is'),
                    ('who',  'is', 'the'),
                    ('who',  'is'))
        match = None
        for prefix in prefices:
            try:
                # Look for the prefix in the words
                (start, end, score) = fuzzy_list_range(words, prefix)
                LOG.debug("%s matches %s with from %d to %d with score %d",
                          prefix, words, start, end, score)
                if start == 0 and (match is None or match[2] < score):
                    match = (start, end, score)
            except ValueError:
                pass

        # If we got a good match then use it
        if match:
            (start, end, score) = match
            thing = ' '.join(words[end:]).strip().lower()

            # Let's look to see if Wikipedia returns anything when we search
            # for this thing
            best = None
            try:
                self._notify(Notifier.ACTIVE)
                for result in wikipedia.search(thing):
                    if result is None or len(result) == 0:
                        continue
                    score = fuzz.ratio(thing, result.lower())
                    LOG.debug("'%s' matches '%s' with a score of %d",
                              result, thing, score)
                    if best is None or best[1] < score:
                        best = (result, score)
            except Exception as e:
                LOG.error("Failed to query Wikipedia for '%s': %s" %
                          (thing, e))
            finally:
                self._notify(Notifier.IDLE)

            # Turn the words into a string for the handler
            if best is not None:
                return _Handler(self, tokens, best[1] / 100, best[0])

        # If we got here then it didn't look like a query for us
        return None

