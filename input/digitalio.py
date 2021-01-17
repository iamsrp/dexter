"""
An input which uses the Adafruit `digitalio` interface.
"""

from   dexter.input    import Input, Token
from   dexter.core.log import LOG
from   digitalio       import DigitalInOut, Direction, Pull
from   threading       import Thread

import board
import time

# ------------------------------------------------------------------------------

class VoiceBonnetInput(Input):
    """
    A way to get input from the the Adafruit Voice Bonnet.
    """
    _BUTTON = board.D17

    def __init__(self,
                 state,
                 prefix='Dexter',
                 button='play or pause'):
        """
        @see Input.__init__()
        :type  prefix: str
        :param prefix:
            The prefix to use when sending the inputs.
        :type  button: str
        :param button:
            What string to send when the button is pressed.
        """
        super(VoiceBonnetInput, self).__init__(state)

        def tokenize(string):
            if string and str(string).strip():
                return [Token(word.strip(), 1.0, True)
                        for word in str(string).strip().split()
                        if word]
            else:
                return []

        # What we will spit out when pressed
        self._output = tokenize(prefix) + tokenize(button)

        # The button, we will set these up in _start()
        self._button  = None
        self._pressed = False

        # And where we put the tokens
        self._output = []


    def read(self):
        """
        @see Input.read
        """
        # What we will hand back
        result = None

        # Anything?
        if not self._button.value:
            # Button is pressed
            if not self._pressed:
                # State changed to pressed
                self._pressed = True
                result = self._output
        elif self._pressed:
            # Released
            self._pressed = False


    def _start(self):
        """
        @see Component.start()
        """
        # Create the button
        self._button           = DigitalInOut(board.D17)
        self._button.direction = Direction.INPUT
        self._button.pull      = Pull.UP
