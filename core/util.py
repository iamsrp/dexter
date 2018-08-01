'''
Various utility methods.
'''

from __future__ import (absolute_import, division, print_function, with_statement)

import alsaaudio
import re
import sys

from   dexter.core.log import LOG

# ------------------------------------------------------------------------------

class _WordsToNumbers():
    """
    A class that can translate strings of common English words that describe a
    number into the number described.

    From:
      http://code.activestate.com/recipes/550818-words-to-numbers-english/
    with some minor tweaking.
    """
    # a mapping of digits to their names when they appear in the
    # relative "ones" place (this list includes the 'teens' because
    # they are an odd case where numbers that might otherwise be called
    # 'ten one', 'ten two', etc. actually have their own names as single
    # digits do)
    __ones__ = { 'one':   1, 'eleven':     11,
                 'two':   2, 'twelve':     12,
                 'three': 3, 'thirteen':   13,
                 'four':  4, 'fourteen':   14,
                 'five':  5, 'fifteen':    15,
                 'six':   6, 'sixteen':    16,
                 'seven': 7, 'seventeen':  17,
                 'eight': 8, 'eighteen':   18,
                 'nine':  9, 'nineteen':   19 }

    # a mapping of digits to their names when they appear in the 'tens'
    # place within a number group
    __tens__ = { 'ten':     10,
                 'twenty':  20,
                 'thirty':  30,
                 'forty':   40,
                 'fifty':   50,
                 'sixty':   60,
                 'seventy': 70,
                 'eighty':  80,
                 'ninety':  90 }

    # an ordered list of the names assigned to number groups
    __groups__ = { 'thousand':    1000,
                   'million':     1000000,
                   'billion':     1000000000,
                   'trillion':    1000000000000,
                   'brazillion':  sys.maxint }

    # a regular expression that looks for number group names and captures:
    #     1-the string that preceeds the group name, and
    #     2-the group name (or an empty string if the
    #       captured value is simply the end of the string
    #       indicating the 'ones' group, which is typically
    #       not expressed)
    __groups_re__ = re.compile(
        r'\s?([\w\s]+?)(?:\s((?:%s))|$)' %
        ('|'.join(__groups__))
    )

    # a regular expression that looks within a single number group for
    # 'n hundred' and captures:
    #    1-the string that preceeds the 'hundred', and
    #    2-the string that follows the 'hundred' which can
    #      be considered to be the number indicating the
    #      group's tens- and ones-place value
    __hundreds_re__ = re.compile(r'([\w\s]+)\shundred(?:\s(.*)|$)')

    # a regular expression that looks within a single number
    # group that has already had its 'hundreds' value extracted
    # for a 'tens ones' pattern (ie. 'forty two') and captures:
    #    1-the tens
    #    2-the ones
    __tens_and_ones_re__ =  re.compile(
        r'((?:%s))(?:\s(.*)|$)' %
        ('|'.join(__tens__.keys()))
    )

    def parse(self, words):
        """
        Parses words to the number they describe.
        """
        # to avoid case mismatch, everything is reduced to the lower
        # case
        words = words.lower()
        # create a list to hold the number groups as we find them within
        # the word string
        groups = {}
        # create the variable to hold the number that shall eventually
        # return to the caller
        num = None
        # using the 'groups' expression, find all of the number group
        # an loop through them
        for group in _WordsToNumbers.__groups_re__.findall(words):
            ## determine the position of this number group
            ## within the entire number
            # assume that the group index is the first/ones group
            # until it is determined that it's a higher group
            group_multiplier = 1
            if group[1] in _WordsToNumbers.__groups__:
                group_multiplier = _WordsToNumbers.__groups__[group[1]]
            ## determine the value of this number group
            # create the variable to hold this number group's value
            group_num = 0
            # get the hundreds for this group
            hundreds_match = _WordsToNumbers.__hundreds_re__.match(group[0])
            # and create a variable to hold what's left when the
            # "hundreds" are removed (ie. the tens- and ones-place values)
            tens_and_ones = None
            # if there is a string in this group matching the 'n hundred'
            # pattern
            if hundreds_match is not None and hundreds_match.group(1) is not None:
                # multiply the 'n' value by 100 and increment this group's
                # running tally
                group_num = group_num + \
                            (_WordsToNumbers.__ones__[hundreds_match.group(1)] * 100)
                # the tens- and ones-place value is whatever is left
                tens_and_ones = hundreds_match.group(2)
            else:
                # if there was no string matching the 'n hundred' pattern,
                # assume that the entire string contains only tens- and ones-
                # place values
                tens_and_ones = group[0]

            # if the 'tens and ones' string is empty, it is time to
            # move along to the next group
            if tens_and_ones is None:
                # increment the total number by the current group number, times
                # its multiplier
                if num is None:
                    num = 0
                num = num + (group_num * group_multiplier)
                continue
            # look for the tens and ones ('tn1' to shorten the code a bit)
            tn1_match = _WordsToNumbers.__tens_and_ones_re__.match(tens_and_ones)
            # if the pattern is matched, there is a 'tens' place value
            if tn1_match is not None:
                # add the tens
                group_num = group_num + _WordsToNumbers.__tens__[tn1_match.group(1)]
                # add the ones
                if tn1_match.group(2) is not None:
                    group_num = group_num + _WordsToNumbers.__ones__[tn1_match.group(2)]
            else:
                # assume that the 'tens and ones' actually contained only the ones-
                # place values
                group_num = group_num + _WordsToNumbers.__ones__[tens_and_ones]
            # increment the total number by the current group number, times
            # its multiplier
            if num is None:
                num = 0
            num = num + (group_num * group_multiplier)
        # the loop is complete, return the result
        return num

# ------------------------------------------------------------------------------

_WORDS_TO_NUMBERS = _WordsToNumbers()

_LOWER   = ''.join(chr(i) for i in range(ord('a'), ord('z') + 1))
_UPPER   = _LOWER.upper()
_NUMBERS = ''.join(str(i) for i in range(0, 10))

# ------------------------------------------------------------------------------

def _strip_to(string, alphabet):
    '''
    Remove non-alphabet contents from a word.

    @type   string: str
    @parses string:
       The string to strip the chars from.

    @rtype: str
    @return:
        The stripped string.
    '''
    return ''.join(char
                   for char in string
                   if  char in alphabet)


def to_letters(string):
    '''
    Remove non-letters from a string.

    @type   string: str
    @parses string:
       The string to strip the chars from.

    @rtype: str
    @return:
        The stripped string.
    '''
    return _strip_to(string, _UPPER + _LOWER)


def to_alphanumeric(string):
    '''
    Remove non-letters and non-numbers from a string.

    @type   string: str
    @parses string:
       The string to strip the chars from.

    @rtype: str
    @return:
        The stripped string.
    '''
    return _strip_to(string, _UPPER + _LOWER + _NUMBERS)


def parse_number(words):
    '''
    Turn a set of words into a number. These might be complex ("One thousand
    four hundred and eleven") or simple ("Seven").

    >>> to_number('one')
    1
    >>> to_number('one point eight')
    1

    @type  words: str
    @parse words:
        The string words to parse. E.g. C{'twenty seven'}.
    '''
    # Sanity
    if words is None:
        return None

    # Make sure it's a string
    words = str(words)

    # Trim surrounding whitespace
    words = words.strip()

    # Not a lot we can do if we have no words
    if len(words) == 0:
        return None

    # First try to parse the string as an integer or a float directly
    if not re.search(r'\s', words):
        try:
            return int(words)
        except:
            pass
        try:
            return float(words)
        except:
            pass

    # Sanitise it since we're now going to attempt to parse it. Collapse
    # multiple spaces to one and strip out non-letters
    words = to_letters(' '.join(re.split(r'\s+', words)))

    # Recheck for empty
    if words == '':
        return None

    # Look for "point" in the words since it might be "six point two" or
    # something
    if ' point ' in words:
        # Determine the integer and decimal portions
        (integer, decimal) = words.split(' point ', 1)

        # Parsing the whole number is easy enough
        whole = parse_number(integer)
        if whole is None:
            return None

        # S;plit up the digits to parse them. This isn't entirely robust since
        # someone might say "six point twenty nine" but we'll kinda ignore that
        # and hope for the best.
        digits = [parse_number(digit)
                  for digit in decimal.split(' ')]
        if None in digits:
            return None

        # Okay, use some cheese to parse into a float
        return float('%d.%s' % (whole, ''.join(str(d) for d in digits)))

    else:
        # No ' point ' in it, parse directly
        return _WORDS_TO_NUMBERS.parse(words)


def list_index(list, sublist, start=0):
    '''
    Find the index of of a sublist in a list.

    @type  list: list
    @param list:
        The list to look in.
    @type  sublist: list
    @param sublist:
        The list to look for.
    @type  start: int
    @param start:
        Where to start looking in the C{list}.
    '''
    # The empty list can't be in anything
    if len(sublist) == 0:
        raise ValuError("Empty sublist not in list")

    # Simple case
    if len(sublist) == 1:
        return list.index(sublist[0], start)

    # Okay, we have multiple elements in our sublist. Look for the first
    # one, and see that it's adjacent to the rest of the list. We
    offset = start
    while True:
        try:
            first = list_index(list, sublist[ :1], offset)
            rest  = list_index(list, sublist[1: ], first + 1)
            if first + 1 == rest:
                return first

        except ValueError:
            raise ValueError('%s not in %s' % (sublist, list))

        # Move the offset to be after the first instance of sublist[0], so
        # that we may find the next one, if any
        offset = first + 1

# ----------------------------------------------------------------------

def set_volume(value):
    '''
    Set the volume to a value between zero and eleven.
    '''
    volume = float(value)

    if volume < 0 or volume > 11:
        raise ValueError("Volume out of [0..11] range: %s" % value)

    # Get the ALSA mixer. We should probably handle pulse audio at some point
    # too I guess.
    try:
        m = alsaaudio.Mixer()
    except:
        m = alsaaudio.Mixer('PCM')

    # Set as a percentage
    pct = int((volume / 11) * 100)
    LOG.info("Setting volume to %d%%" % pct)
    m.setvolume(pct)
