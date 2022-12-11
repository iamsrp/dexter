"""
How Dexter sends information to the outside world.

This might be via speech synthesis, a display, logging, etc.
"""

from   dexter.core      import Component
from   dexter.core.log  import LOG
from   dexter.core.util import to_letters

import math

# ------------------------------------------------------------------------------

class Output(Component):
    """
    A way to get information to the outside world.
    """
    def __init__(self, state):
        """
        :type  state: `State`
        :param state:
            The global State instance.
        """
        super(Output, self).__init__(state)


    @property
    def is_output(self):
        """
        Whether this component is an output.
        """
        return True


    def write(self, text):
        """
        Send the given text to the outside world.

        :type  text: str
        :param text:
            What to write.
        """
        # Subclasses should implement this
        raise NotImplementedError("Abstract method called")


class SpeechOutput(Output):
    """
    An output which generates audio speech.

    When one of these classes has a state which is not ``IDLE`` we deem it to be
    generating audio on the speaker.
    """
    # How we turn letters into they phonetic versions
    _LETTERIFY = {
        'a' : 'aay',
        'b' : 'bee',
        'c' : 'see',
        'd' : 'dee',
        'e' : 'ee',
        'f' : 'eff',
        'g' : 'jee',
        'h' : 'aych',
        'i' : 'eye',
        'j' : 'jay',
        'k' : 'kay',
        'l' : 'el',
        'm' : 'em',
        'n' : 'en',
        'o' : 'owe',
        'p' : 'pee',
        'q' : 'queue',
        'r' : 'are',
        's' : 'ess',
        't' : 'tee',
        'u' : 'you',
        'v' : 'vee',
        'w' : 'double you',
        'x' : 'ex',
        'y' : 'why',
        'z' : 'zee',
    }

    # How we turn symbols into their named version
    _WORDIFY = {
        '#'  : 'hash',
        '$'  : 'dollar',
        '%'  : 'percent',
        '&'  : 'and',
        '*'  : 'star',
        '+'  : 'plus',
        '/'  : 'slash',
        '<'  : 'less than',
        '='  : 'equals',
        '>'  : 'greater than',
        '@'  : 'at',
        '\\' : 'back slash',
        '^'  : 'caret',
        '_'  : '', # Ignore
        '`'  : 'back tick',
        '|'  : 'pipe',
        '~'  : 'tilde',
    }


    @property
    def is_speech(self):
        """
        @see Component.is_speech()
        """
        return True


    def _speechify(self, text):
        """
        Take the given input text and preprocess it so that it sounds more correct
        when spoken. This is done via turning abbreviations into their letters.

        This function will loko for all the other member functions of the form
        `_speechify_N_blah` where `N` is a single-digit priority, with a lower
        value meaning a higher priority. It will then apply each function in
        priority order, stopping when a function gives back a non-None result.
        """
        if text is None or text == '':
            return text

        # We'll give this back
        result = ''

        # Process one word at a time
        for word in text.split():
            # Strip punctuation
            punc = ''
            while len(word) > 0 and word[-1] in '.?!,:':
                punc = punc + word[-1]
                word = word[:-1]

            # Now apply all the functions
            for name in [n
                         for n in sorted(dir(self))
                         if n.startswith('_speechify_')]:
                f = getattr(self, name)
                new = f(word)
                if new is not None:
                    LOG.debug("Used %s() to turn '%s' into '%s'",
                              name, word, new)
                    break

            # Did we get anything?
            if new is None:
                new = word
            if len(result) > 0:
                result += ' '

            # Put it in, along with any punctuation
            result += new + punc

        # Say if we tweaked it
        if text != result:
            LOG.info("Turned '%s' into '%s'", text, result)

        # And give back whatever we had
        return result

        
    def _speechify_2_symbols(self, word):
        """
        Handle things like '!=' etc.
        """
        changed = False
        for (symbol, name) in (('!=', ' not equal to '          ),
                               ('~=', ' approximately equal to '),
                               ('+=', ' plus equals '           ),
                               ('-=', ' minus equals '          ),
                               ('*=', ' times equals '          ),
                               ('/=', ' divide equals '         ),
                               ('|=', ' or equals '             ),
                               ('&=', ' an equals '             ),
                               ('||', ' or '                    ),
                               ('&&', ' and '                   ),):
            if symbol in word:
                word = word.replace(symbol, name)
                changed = True
        if changed:
            return word.strip()
        else:
            return None

        
    def _speechify_4_number(self, number):
        """
        Turn a raw number string into something which sounds good.
        """
        # See if it's a number
        try:
            value = float(number)
        except ValueError:
            return None

        # Strip any leading '+' symbol, it's superfluous
        if number.startswith('+'):
            number = number[1:]

        # Handle floating point noise
        tweaked = math.copysign(abs(value + 1e-13), value)
        if int(value) != int(tweaked):
            number = str(tweaked)

        # Avoid -0.0 by handling it specifically
        if value == 0:
            return "zero"

        # Handle values with exponents in them
        if 'e' in number:
            # Break it up, rendering the exponent accordingly
            (number, exp) = number.split('e')
            exponent = ('times ten to the power of %s' %
                        self._speechify_4_number(exp))
        else:
            exponent = ''

        # Since this is going to be spoken we will explictily state "foo
        # point b a r" since the period in 'foo.bar' might be interpreted as
        # a full stop by some TTS engines and the digits should be spoken
        # separately.
        parts = number.split('.')
        if len(parts) == 2:
            # We have a fractional number. Let's not go crazy with precision
            whole = parts[0]
            if len(parts[1]) > 8:
                frac   = parts[1][:8]
                approx = 'approximately '
            else:
                frac   = parts[1]
                approx = ''

            # Strip any trailing zeroes and any empty decimal point from
            # decimal values
            frac = frac.rstrip('0')
            if frac != '':
                number = '%s%s point %s' % (approx, whole, (' '.join(frac)))
            else:
                number = '%s%s' % (approx, whole)

        # Put back any exponent
        if exponent:
            number = f'{number} {exponent}'

        # And give it back
        return number

        
    def _speechify_5_abbrev(self, abbrev):
        """
        Turn an abbreviation into letters.
        """
        # See if the string was an allcaps one, possibly with periods in it
        if abbrev is not None       and \
           abbrev.upper() == abbrev and \
           len(to_letters(abbrev)) > 1:
            # Break up the letters into chars and render their names. We ignore
            # periods in the string when we do this (i.e. "ACE" vs "A.C.E.").
            return ' '.join(self._LETTERIFY.get(letter, letter)
                            for letter in abbrev.lower()
                            if letter != '.')
        else:
            # Guess not
            return None

        
    def _speechify_5_chars(self, word):
        """
        Handle things like slash, backslash, etc.
        """
        # Break up the word into chars and look for special ones
        changed = False
        result = []
        for char in word:
            if char in self._WORDIFY:
                # Put spaces around the rendered word since we will stitch back
                # without them
                result.append(' %s ' % self._WORDIFY[char])
                changed = True
            else:
                result.append(char)

        if changed:
            # And stitch it all back together
            return ''.join(result)
        else:
            return None
                               
