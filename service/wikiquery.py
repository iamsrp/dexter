"""
Pull information from Wikipedia.
"""

import wikipedia

from   dexter.core      import Notifier
from   dexter.core.log  import LOG
from   dexter.core.util import list_index
from   dexter.service   import Service, Handler, Result

class _Handler(Handler):
    """
    The handler for Wikipedia queries.
    """
    def __init__(self, service, tokens, belief, thing):
        """
        @see Handler.__init__()

        @type  thing: str
        @param thing:
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
            summary = wikipedia.summary(self._thing)
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
        if '. ' in shortened and len(shortened) > 400:
            index = shortened.index('. ')
            shortened = shortened[:index+1]

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
        prefices = (('what', 'is'),
                    ('who', 'is'))
        for prefix in prefices:
            try:
                # Look for the prefix in the words
                index = list_index(words, prefix)

                # If we got here then we found the prefix. Strip that from the
                # query which we are about to make to Wikipedia.
                thing = ' '.join(words[index + len(prefix):]).strip()

                # Let's look to see if Wikipedia returns anything when we search
                # for this thing.
                belief = 0.5
                try:
                    self._notify(Notifier.ACTIVE)
                    results = [result.lower().strip()
                               for result in wikipedia.search(thing)
                               if result is not None and len(result) > 0]
                    if thing in results:
                        belief = 1.0
                except Exception as e:
                    LOG.error("Failed to query Wikipedia for '%s': %s" %
                              (thing, e))
                finally:
                    self._notify(Notifier.IDLE)

                # Turn the words into a string for the handler.
                return _Handler(self, tokens, belief, thing)

            except Exception as e:
                LOG.debug("%s not in %s: %s" % (prefix, words, e))
                

        # If we got here then it didn't look like a query for us.
        return None

