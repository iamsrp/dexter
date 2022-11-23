"""
Services relating to numbers in various ways.
"""

from dexter.service          import Service, Handler, Result
from dexter.core.arithmetic  import (Constant, Identity,
                                     ConstantE, ConstantPi, ConstantTau,
                                     Add, Subtract, Multiply, Divide,
                                     Square, Cube,
                                     SquareRoot, CubeRoot,
                                     Sine, Cosine, Tangent,
                                     Log, NaturalLog, Log2,
                                     Factorial)
from dexter.core.log         import LOG
from dexter.core.util        import (fuzzy_list_range,
                                     parse_number,
                                     to_alphanumeric)
from fuzzywuzzy              import fuzz

# ----------------------------------------------------------------------

class _CalculatorHandler(Handler):
    def __init__(self, service, tokens, value):
        """
        @see Handler.__init__()

        :type value: arithmetic._Value
        :param value:
            The value to evaluate.
        """
        super().__init__(service, tokens, 1.0, True)
        self._value = value


    def handle(self):
        """
        @see Handler.handle()
        """
        try:
            # Compute it. See if the result is "exact" or not, and give it all
            # back to the user as a nice string.
            value = self._value()
            strval05 = ('%0.5f'  % value).rstrip('0').rstrip('.')
            strval15 = ('%0.15f' % value).rstrip('0').rstrip('.')
            approx = '' if strval05 == strval15 else 'approximately '
            result = f'{str(self._value)} is {approx}{strval05}'
        except Exception as e:
            error = to_alphanumeric(str(e))
            result = f'Sorry, I could not compute {self._value}: {error}'
        return Result(self, result, True, False)


class CalculatorService(Service):
    """
    A service which works as a simple calculator.
    """

    _CONSTANTS = (
        ('e',   ConstantE),
        ('ee',  ConstantE),
        ('pi',  ConstantPi),
        ('pie', ConstantPi),
        ('tau', ConstantTau),
    )

    _PREFIX_FUNCTIONS = (
        # These might have a 'the' prefix as well as an 'of' postfix
        ('value',       Identity),
        ('square root', SquareRoot),
        ('cube root',   CubeRoot),
        ('square',      Square),
        ('cube',        Cube),
        ('factorial',   Factorial),
        ('sine',        Sine),
        ('sign',        Sine),
        ('cosine',      Cosine),
        ('tan',         Tangent),
        ('tangent',     Tangent),
        ('log',         Log),
        ('log e',       NaturalLog),
        ('natrual log', NaturalLog),
        ('log 2',       Log2),
        ('log two',     Log2),
    )

    _POSTFIX_FUNCTIONS = (
        ('squared',   Square),
        ('cubed',     Cube),
        ('factorial', Factorial),
    )

    _INFIX_FUNCTIONS = (
        # Order is important so that we bind with * and / before + and -.
        ('times',         Multiply),
        ('multiplied by', Multiply),
        ('divided by',    Divide),
        ('plus',          Add),
        ('minus',         Subtract),
    )

    def __init__(self, state):
        """
        @see Service.__init__()
        """
        super().__init__("Calculator", state)


    def evaluate(self, tokens):
        """
        @see Service.evaluate()
        """
        # Maybe we'll make this a parameter at some point
        threshold = 75

        # Render to lower-case, for matching purposes.
        words = self._words(tokens)

        # Look for these types of question
        prefices = (('what', 'is'),
                    ('what', 'is', 'the', 'value', 'of'))
        match = None
        for prefix in prefices:
            try:
                # Look for the prefix in the words
                (start, end, score) = fuzzy_list_range(words, prefix)
                LOG.debug("%s matches %s with from %d to %d with score %d",
                          prefix, words, start, end, score)
                if score >= threshold and \
                   start == 0         and \
                   (match is None or match[1] < score):
                    LOG.debug("Matched '%s' with score %d for '%s'",
                              ' '.join(prefix),
                              score,
                              ' '.join(words))
                    match = (words[end:], score)
            except ValueError:
                pass

        # If we got nothing then we are done
        if match is None:
            return None

        # Attempt to parse what we are given into a mathematical expression. If
        # that works then we can create a handler to evaluate it.
        expression = [to_alphanumeric(word) for word in match[0]]
        LOG.debug("Attempting to evaluate expression '%s'", ' '.join(expression))
        value = self._make_value(expression, threshold)
        if value is None:
            return None
        else:
            LOG.debug("Got value tree: %s", str(value))
            return _CalculatorHandler(self, tokens, value)


    def _make_value(self, words, threshold):
        """
        Turn the given words into a `_Value`.
        """
        # Nothing breeds nothing
        if words is None or len(words) == 0:
            return None

        # Handle all the possible matches in least-binding order. This will try
        # to ensure that we match an expression correctly since the most
        # binding functions should be at the leaves of the tree and the least
        # binding ones at the root. The semantics are ambiguous though, since
        # binding semantics can be a little iffy without brackets.
        LOG.debug("Making a value with '%s'", ' '.join(words))

        # Infix functions, like "6 times 9" (which is 42, if you've read the
        # books that far)
        for (func, cls) in self._INFIX_FUNCTIONS:
            try:
                (start, end, score) = fuzzy_list_range(words, func.split())
                if score > threshold:
                    # We got a match, so the bits before and after should be
                    # _Values too
                    LOG.debug("Matched infix '%s'", func)
                    v0 = self._make_value(words[   :start], threshold)
                    v1 = self._make_value(words[end:     ], threshold)
                    if v0 is not None and v1 is not None:
                        # That worked so build it and return it
                        return cls(v0, v1)
            except ValueError:
                pass

        # Postfix functions, like "10 squared"
        for (func, cls) in self._POSTFIX_FUNCTIONS:
            try:
                (start, end, score) = fuzzy_list_range(words, func.split())
                if end == len(words) and score > threshold:
                    # We got a match, so attempt to turn the bits before it
                    # into a value
                    LOG.debug("Matched postfix '%s'", func)
                    v = self._make_value(words[:start], threshold)
                    if v is not None:
                        # That worked so build it and return it
                        return cls(v)
            except ValueError:
                pass

        # Prefix functions, like "the square root of 49"
        for (func, cls) in self._PREFIX_FUNCTIONS:
            for pre in ([], ['the']):
                for post in ([], ['of']):
                    prefix = pre + func.split() + post
                    try:
                        (start, end, score) = fuzzy_list_range(words, prefix)
                        if start == 0 and score > threshold:
                            # We got a match, so attempt to turn the rest of the
                            # words into a _Value to operate on
                            LOG.debug("Matched prefix '%s'", func)
                            v = self._make_value(words[end:], threshold)
                            if v is not None:
                                # That worked so build it and return it
                                return cls(v)
                    except ValueError:
                        pass

        # Constants are full strings
        constant = parse_number(' '.join(words))
        if constant is not None:
            LOG.debug("Matched constant value %f", constant)
            return Constant(constant)
        if len(words) == 1:
            word = words[0]
            for (constant, cls) in self._CONSTANTS:
                if fuzz.ratio(constant, word) > threshold:
                    LOG.debug("Matched constant %f", constant)
                    return cls()

        # If we got this far then nothing worked
        return None
