"""
Mathematical functions, at a basic level.
"""

import math

class _Value:
    """
    Something which may be evaluated to yield a value.
    """
    def __call__(self):
        """
        The ``()`` method, which subclass must implement.
        """
        raise NotImplementedError()


class _Function(_Value):
    """
    A value gained by calling a function on another.
    """
    def __init__(self, v):
        self._v = v

    
    @property
    def v(self):
        return self._v()


    @property
    def _description(self):
        """
        The description, used to stringify the function.
        """
        raise NotImplementedError()


    def __str__(self):
        return f'{self._description} {self._v}'


class _BiFunction(_Value):
    """
    A value gained by calling a function on two others.
    """
    def __init__(self, v0, v1):
        self._v0 = v0
        self._v1 = v1


    @property
    def v0(self):
        return self._v0()


    @property
    def v1(self):
        return self._v1()


    @property
    def _description(self):
        """
        The description, used to stringify the bi-function.
        """
        raise NotImplementedError()


    def __str__(self):
        return f'{self._v0} {self._description} {self._v1}'


class Constant(_Value):
    """
    A constant floating point value.
    """
    def __init__(self, constant):
        self._constant = float(constant)


    def __call__(self):
        return self._constant


    def __str__(self):
        return ('%0.7f' % self._constant).rstrip('0').rstrip('.')


class ConstantE(Constant):
    """
    The constant ``e``.
    """
    def __init__(self):
        super().__init__(math.e)


    def __str__(self):
        return 'e'


class ConstantPi(Constant):
    """
    The constant ``pi``.
    """
    def __init__(self):
        super().__init__(math.pi)


    def __str__(self):
        return 'pi'


class ConstantTau(Constant):
    """
    The constant ``tau``.
    """
    def __init__(self):
        super().__init__(math.tau)


    def __str__(self):
        return 'tau'


class Add(_BiFunction):
    """
    A value gained by adding two other values together.
    """
    def __call__(self):
        return self.v0 + self.v1


    @property
    def _description(self):
        return "plus"


class Subtract(_BiFunction):
    """
    A value gained by subtracting one value from another.
    """
    def __call__(self):
        return self.v0 - self.v1


    @property
    def _description(self):
        return "minus"
    

class Multiply(_BiFunction):
    """
    A value gained by multiplying two values together.
    """
    def __call__(self):
        return self.v0 * self.v1


    @property
    def _description(self):
        return "times"


class Divide(_BiFunction):
    """
    A value gained by dividing one value by another.
    """
    def __call__(self):
        return self.v0 / self.v1


    @property
    def _description(self):
        return "divided by"


class Power(_BiFunction):
    """
    A value gained by raising one value to the power of another.
    """
    def __call__(self):
        return math.pow(self.v0, self.v1)


    @property
    def _description(self):
        return "to the power of"


class Identity(_Function):
    """
    A value which is just itself.
    """
    def __init__(self, v):
        super().__init__(v)


    @property
    def _description(self):
        return "the value of"


    def __call__(self):
        return self.v


class Negate(_Function):
    """
    A value gained by negating another.
    """
    def __call__(self):
        return -self.v


    @property
    def _description(self):
        return "negative"


class Square(_Function):
    """
    A value gained by taking the square of another.
    """
    def __init__(self, v):
        super().__init__(v)


    @property
    def _description(self):
        return "the square of"


    def __call__(self):
        return math.pow(self.v, 2)


class Cube(_Function):
    """
    A value gained by taking the cube of another.
    """
    def __init__(self, v):
        super().__init__(v)


    @property
    def _description(self):
        return "the cube of"


    def __call__(self):
        return math.pow(self.v, 3)


class SquareRoot(_Function):
    """
    A value gained by taking the square root of another.
    """
    def __init__(self, v):
        super().__init__(v)


    @property
    def _description(self):
        return "the square root of"


    def __call__(self):
        return math.pow(self.v, 1/2)


class CubeRoot(_Function):
    """
    A value gained by taking the cube root of another.
    """
    def __init__(self, v):
        super().__init__(v)


    @property
    def _description(self):
        return "the cube root of"


    def __call__(self):
        return math.pow(self.v, 1/3)


class Factorial(_Function):
    """
    A value gained by computing the factorial of another.
    """
    def __call__(self):
        return math.factorial(self.v)


    @property
    def _description(self):
        return "factorial of"


class Sine(_Function):
    """
    A value gained by computing the sine of another.
    """
    def __call__(self):
        return math.sin(self.v)


    @property
    def _description(self):
        return "sine of"


class Cosine(_Function):
    """
    A value gained by computing the cosine of another.
    """
    def __call__(self):
        return math.cos(self.v)


    @property
    def _description(self):
        return "cosine of"


class Tangent(_Function):
    """
    A value gained by computing the tangent of another.
    """
    def __call__(self):
        return math.tan(self.v)


    @property
    def _description(self):
        return "tan of"


class Log(_Function):
    """
    A value gained by computing log10 of another.
    """
    def __call__(self):
        return math.log10(self.v)


    @property
    def _description(self):
        return "log of"


class NaturalLog(_Function):
    """
    A value gained by computing the natural log of another.
    """
    def __call__(self):
        return math.log(self.v)


    @property
    def _description(self):
        return "natural log of"


class Log2(_Function):
    """
    A value gained by computing log2 of another.
    """
    def __call__(self):
        return math.log2(self.v)


    @property
    def _description(self):
        return "log 2 of"
