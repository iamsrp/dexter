"""
An input which uses the Raspberry Pi GPIO interface.
"""

from   dexter.input    import Input, Token
from   dexter.core.log import LOG
from   gpiozero        import Button

import time

# ------------------------------------------------------------------------------

class _HatMiniInput(Input):
    """
    A way to get input from the the Pimoroni Scroll HAT Mini.
    """
    _A_BUTTON =  5
    _B_BUTTON =  6
    _X_BUTTON = 16
    _Y_BUTTON = 24

    def __init__(self,
                 state,
                 prefix  ='Dexter',
                 a_button='raise the volume',
                 b_button='lower the volume',
                 x_button='stop',
                 y_button='play or pause'):
        """
        @see Input.__init__()
        :type  prefix: str
        :param prefix:
            The prefix to use when sending the inputs.
        :type  a_button: str
        :param a_button:
            What string to send when the A button is pressed.
        :type  b_button: str
        :param b_button:
            What string to send when the B button is pressed.
        :type  x_button: str
        :param x_button:
            What string to send when the X button is pressed.
        :type  y_button: str
        :param y_button:
            What string to send when the Y button is pressed.
        """
        super(_HatMiniInput, self).__init__(state)

        def tokenize(string):
            if string and str(string).strip():
                return [Token(word.strip(), 1.0, True)
                        for word in str(string).strip().split()
                        if word]
            else:
                return []

        # Our bindings etc.
        self._prefix = tokenize(prefix)
        self._bindings = {
            self._A_BUTTON : tokenize(a_button),
            self._B_BUTTON : tokenize(b_button),
            self._X_BUTTON : tokenize(x_button),
            self._Y_BUTTON : tokenize(y_button),
        }

        # The buttons, we will set these up in _start()
        self._a_button = None
        self._b_button = None
        self._x_button = None
        self._y_button = None

        # And where we put the tokens
        self._output = []


    def read(self):
        """
        @see Input.read
        """
        if len(self._output) > 0:
            try:
                return self._output.pop()
            except:
                pass


    def _start(self):
        """
        @see Component.start()
        """
        # Create the buttons
        self._a_button = Button(self._A_BUTTON)
        self._b_button = Button(self._B_BUTTON)
        self._x_button = Button(self._X_BUTTON)
        self._y_button = Button(self._Y_BUTTON)

        # And bind
        self._a_button.when_pressed = self._on_button
        self._b_button.when_pressed = self._on_button
        self._x_button.when_pressed = self._on_button
        self._y_button.when_pressed = self._on_button


    def _stop(self):
       """
       @see Input.stop
       """
       try:
           self._a_button.close()
           self._b_button.close()
           self._x_button.close()
           self._y_button.close()
       except:
           pass


    def _on_button(self, button):
        """
        Handle a button press.
        """
        number = button.pin.number
        LOG.info("Got button on pin GPIO%d" % (number,))
        tokens = self._bindings.get(number, [])
        if len(tokens) > 0:
            self._output.append(tuple(self._prefix + tokens))



class ScrollHatMiniInput(_HatMiniInput):
    """
    A way to get input from the the Pimoroni Scroll HAT Mini.
    """
    pass



class UnicornHatMiniInput(_HatMiniInput):
    """
    A way to get input from the the Pimoroni Unicorn HAT Mini.
    """
    pass
