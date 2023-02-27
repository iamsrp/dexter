"""
Services to do with the necessities of life.
"""

from   dexter.service     import Service, Handler, Result
from   dexter.core.log    import LOG
from   dexter.core.util   import (fuzzy_list_range,
                                  parse_number,
                                  to_alphanumeric)
from   fuzzywuzzy.process import fuzz

import json
import os

# ----------------------------------------------------------------------

class _ListAddHandler(Handler):
    """
    Add something to the shopping list.
    """
    def __init__(self, service, tokens, what, belief):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, belief, True)
        self._what = what


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            self.service.add(self._what)
            return Result(
                self,
                "Okay, I added %s to your shopping list" % (
                    ' '.join(self._what)
                ),
                True,
                False
            )
        except Exception as e:
            LOG.error("Could not add %s to the shopping list: %s",
                      ' '.join(self._what),
                      e)
            return Result(
                self,
                "Sorry, there was a problem adding %s to your shopping list" % (
                    ' '.join(self._what)
                ),
                False,
                False
            )


class _ListRemoveHandler(Handler):
    """
    Remove something from the shopping list.
    """
    def __init__(self, service, tokens, what, belief):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, belief, True)
        self._what = what


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            self.service.remove(self._what)
            return Result(
                self,
                "Okay, I removed %s from your shopping list" % (
                    ' '.join(self._what)
                ),
                True,
                False
            )
        except Exception as e:
            LOG.error("Could not add %s to the shopping list: %s",
                      ' '.join(self._what),
                      e)
            return Result(
                self,
                "Sorry, there was a problem adding %s to your shopping list" % (
                    ' '.join(self._what)
                ),
                False,
                False
            )


class _ListClearHandler(Handler):
    """
    Clear the shopping list.
    """
    def __init__(self, service, tokens, what, belief):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, belief, True)


    def handle(self):
        """
        @see Handler.handle()
        """
        self.service.clear()
        return Result(
            self,
            "Okay, I cleared your shopping list",
            True,
            False
        )


class _GetListHandler(Handler):
    """
    Get the shopping list.
    """
    def __init__(self, service, tokens, belief):
        """
        @see Handler.__init__()
        """
        super().__init__(service, tokens, belief, True)


    def handle(self):
        """
        @see Handler.handle()
        """
        lst = self.service.get()
        if lst:
            # We have stuff!
            response = \
                "Your shopping list contains:\n%s." % (
                    ',\n'.join(
                        "%d %s" % (
                            v,
                            (self.service.singularise(k) if v == 1 else
                             self.service.pluralise  (k))
                        ) for (k, v) in lst.items()
                    )
                )
        else:
            # Nothing to see here, move along please...
            response = "Your shopping list is empty"

        # And give it back
        return Result(self, response, True, False)


class ShoppingListService(Service):
    """
    A service which simply parrots back what was given to it.
    """
    # Some wordlists which we will want to match
    _MY_LIST  = 'my shopping list'         .split()
    _ON_TO    = 'on to my shopping list'   .split()
    _TO       = 'to my shopping list'      .split()
    _ON       = 'on my shopping list'      .split()
    _OFF      = 'off my shopping list'     .split()
    _FROM     = 'from my shopping list'    .split()
    _WHATS_ON = 'whats on my shopping list'.split()

    # Things which might be pluralised
    _PLURALS_OF = (
        ('packets of ', 'packet of '),
        ('bags of ',    'bag of '),
        ('boxes of ',   'box of '),
        ('cans of ',    'can of '),
        ('tins of ',    'tin of '),
        ('pints of ',   'pint of '),
        ('gallons of ', 'gallon of '),
    )

    def __init__(self, state, filename=None):
        """
        @see Service.__init__()
        """
        super().__init__("ShoppingList", state)

        self._filename = str(filename) if filename else None
        self._list     = dict()


    def add(self, what):
        """
        Add items to the shopping list.
        """
        (item, count) = self._normalise(what)
        if count is None:
            count = 1
        count = self._list.get(item, 0) + count
        self._list[item] = count
        self._save()


    def remove(self, what):
        """
        Remove items from the shopping list.
        """
        (item, count) = self._normalise(what)
        if item in self._list:
            if count is None:
                del self._list[item]
            else:
                count = self._list.get(item, 0) - count
                if count > 0:
                    self._list[item] = count
                else:
                    del self._list[item]

            self._save()


    def clear(self):
        """
        Empty the shopping list.
        """
        self._list = dict()
        self._save()


    def get(self):
        """
        Get the shopping list. Do not mutate this.
        """
        return self._list


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # A reasonable matching threshold
        threshold = 75

        # Render to lower-case, for matching purposes.
        words = self._words(tokens)

        # Look for "Add blah to my shopping list" or "Put blah on [to] my shopping
        # list"
        match = None
        for (action, phrases, handler) in (
                ("add",    (self._ON_TO, self._TO, self._ON), _ListAddHandler),
                ("put",    (self._ON_TO, self._TO, self._ON), _ListAddHandler),
                ("take",   (self._OFF,   self._FROM        ), _ListRemoveHandler),
                ("remove", (self._OFF,   self._FROM        ), _ListRemoveHandler),
                ("delete", (self._OFF,   self._FROM        ), _ListRemoveHandler),
                ("clear",  (self._MY_LIST,                 ), _ListClearHandler),
                ("reset",  (self._MY_LIST,                 ), _ListClearHandler),
        ):
            if len(words) >= 4 and words[0] == action:
                # Look to match the phrase
                for phrase in phrases:
                    try:
                        # Look for the prefix in the words
                        (start, end, score) = fuzzy_list_range(words, phrase)
                        LOG.debug("%s matches %s with from %d to %d with score %d",
                                  phrase, words, start, end, score)
                        if score >= threshold and \
                           (match is None or match[2] < score):
                            LOG.debug("Matched '%s' with score %d for '%s'",
                                      ' '.join(phrase),
                                      score,
                                      ' '.join(words))
                            match = (handler, words[1:start], score)

                    except ValueError:
                        pass

        # Did we get something?
        if match:
            (handler, what, score) = match
            return handler(self, tokens, what, score/100)

        # Now look for a direct query
        for phrase in (['whats', 'on'], ['tell', 'me']):
            phrase = phrase + self._MY_LIST
            try:
                # Look for the prefix in the words
                (start, end, score) = fuzzy_list_range(words, phrase)
                LOG.debug("%s matches %s with from %d to %d with score %d",
                          phrase, words, start, end, score)
                if score >= threshold and \
                   start == 0 and end == len(words):
                    LOG.debug("Matched '%s' with score %d for '%s'",
                              ' '.join(phrase),
                              score,
                              ' '.join(words))
                    return _GetListHandler(self, tokens, score/100)

            except ValueError:
                pass

        # No match
        return None


    def pluralise(self, phrase_):
        """
        Take the string phrase and ensure that it is plural.
        """
        # Null breeds null
        if not phrase_:
            return phrase_

        # Normalise
        words  = self._listify(phrase_)
        phrase = ' '.join(words)

        # Handle 'blah of ...'
        for (plural, singular) in self._PLURALS_OF:
            if phrase.startswith(singular):
                return phrase.replace(singular, plural)

        # Just look for an 's' at the end and assume that it's fine
        if words[-1].endswith('s'):
            return phrase

        # Else we need to put an 's' on the end
        word = words[-1]

        # Special plural forms
        if word.endswith('tch') or word.endswith('ss'):
            # 'watch'    -> 'watches'
            # 'baroness' -> 'baronesses'
            words[-1] = word + 'es'
        elif word.endswith('y'):
            word = word[:-1] + 'ies'
        else:
            # Just add the 's'
            words[-1] = word + 's'

        # Rebuild the phrase and give it back
        return ' '.join(words)


    def singularise(self, phrase_):
        """
        Take the phrase and ensure that it is singularise.
        """
        # Null breeds null
        if not phrase_:
            return phrase_

        # Normalise
        words  = self._listify(phrase_)
        phrase = ' '.join(words)

        # Handle 'blahs of ...'
        for (plural, singular) in self._PLURALS_OF:
            if phrase.startswith(plural):
                return phrase.replace(plural, singular)

        # Plurals end with 's' most of the time; we currently don't handle
        # things like 'funga -> fungi'
        if words[-1].endswith('s'):
            word = words[-1]
            #  Watch out for things like "needless" becoming "needles"
            if word.endswith('ss'):
                # You can't touch this (dah dah-dah dum, tsch-tsch, dah-daaah
                # dum)
                pass

            elif word.endswith('tches') or word.endswith('sses'):
                # 'watches'    -> 'watch'
                # 'baronesses' -> 'baroness'
                words[-1] = word[:-2]

            elif word.endswith('ies'):
                if word in ('cookies',):
                    # Just strip the 's' from these
                    words[-1] = word[:-1]
                else:
                    words[-1] = word[:-3] + 'y'
            else:
                # Just strip the 's'
                words[-1] = word[:-1]

            # Rebuild the phrase and give it back
            return ' '.join(words)

        # Probably fine then, give back the original
        return phrase_


    def _start(self):
        """
        See `Component._start()`.
        """
        self._load()


    def _stop(self):
        """
        See `Component._stop()`.
        """
        self._saveload()


    def _listify(self, phrase):
        """
        Take a pharse and ensure it's a list of words.
        """
        if isinstance(phrase, str):
            return phrase.split()
        elif not isinstance(phrase, list):
            return list(phrase)
        else:
            return phrase


    def _normalise(self, phrase):
        """
        Take a phrase and ensure it's something which can be parsed and used as a
        key in our shopping list dictionary. This means turning articles like
        'a' into '1', number words into their numeric form, and ensuring
        everything is singular.

        We then break these up into an amount and the item name and give them
        back.
        """
        # Null breeds null
        if not phrase:
            return phrase

        # Render it into a list of words, and as a string
        words  = self._listify(phrase)
        phrase = ' '.join(words)

        # Process the phrase into normlised words
        words_ = []
        for word in words:
            # To lower case
            word = word.lower()

            # Get rid of punctuation etc.
            word = to_alphanumeric(word)

            # Turn things into numbers
            if word in ('a', 'an'):
                word = '1'
            else:
                value = parse_number(word)
                if value is not None:
                    word = str(value)

            # Safe to append
            words_.append(word)
        words = words_

        # Preprocess for groups of words which have meaning. Note that any 'a'
        # will have been turned into a '1' above.
        and_a_half    = (('and', '1', 'half'),    '.5')
        and_a_quarter = (('and', '1', 'quarter'), '.25')
        for (group, frac) in (and_a_half, and_a_quarter):
            try:
                # See if we have it
                (start, end, score) = fuzzy_list_range(words, group)
                if start > 0 and end < (len(words)-1) and score > 75:
                    # Splice in the fraction
                    words = (words[:start-1] +
                             [words[start-1] + frac] +
                             words[end:])
            except ValueError:
                pass

        # And '1 dozen' becomes 12 etc.
        for i in range(1, 13):
            try:
                # See if we have it
                (start, end, score) = fuzzy_list_range(words, (str(i), 'dozen'))
                if end < len(words) and score > 75:
                    # Replace it
                    words = (words[:start] + [str(12 * i)] + words[end:])
            except ValueError:
                pass

        # Handle things like "packets of crisps" or "bags of chips"
        try:
            # Look for 'of'
            idx = words.index('of')
            if idx > 0 and idx < len(words-1):
                # Make sure we have "bag of chips" not "bags of chips"
                words[idx-1] = self.singularise(words[idx-1])
        except ValueError:
            # No "of" in there, we'll assume that the last entry is what needs
            # to be singularised
            words[-1] = self.singularise(words[-1])

        # We should have a normalised set of words now. Now we check to see if
        # the first word was a number.
        try:
            # Get it as a number, else throw an exception. Likely we want it to
            # be an int if we can.
            count = float(words[0])
            if int(count) == count:
                count = int(count)

            # And the rest of the words make up the key
            what  = ' '.join(words[1:])

        except ValueError:
            # Nope, so no number that we know of
            count = None
            what  = ' '.join(words)

        # Okay, we now have an item and its amount, so give them back
        return (what, count)


    def _save(self):
        """
        Save our current list to disk, if we have a filename.
        """
        if self._filename:
            try:
                with open(self._filename, 'w') as fh:
                    json.dump(self._list, fh)
                LOG.info("Saved to %s", self._filename)
            except Exception as e:
                LOG.error("Error saving to %s: %s", self._filename, e)


    def _load(self):
        """
        Load our list from disk, if we have a filename.
        """
        if self._filename and os.path.exists(self._filename):
            try:
                with open(self._filename, 'r') as fh:
                    self._list = json.load(fh)
                LOG.info("Loaded from %s", self._filename)
            except Exception as e:
                LOG.error("Error loading from %s: %s", self._filename, e)
