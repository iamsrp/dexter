"""
Notifiers which utilise the tulogic BlinkStick USB dongles.

You will this in ``/etc/udev/rules.d/51-blinkstick.rules``::

    ATTRS{idVendor}=="20a0", ATTRS{idProduct}=="41e5", MODE:="660", GROUP="plugdev"

to make it work. When you have it there, do ``sudo udevadm control --reload``
and unplug and replug in the blinkstick dongle.

@see https://github.com/arvydas/blinkstick-python
"""

from   blinkstick      import blinkstick
from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.notifier import PulsingNotifier
from   threading       import Thread

import math
import time

# ------------------------------------------------------------------------------

class BlinkStickNotifier(PulsingNotifier):
    """
    A notifier for the BlinkStick USB dongle.
    """
    def __init__(self):
        """
        @see PulsingNotifier.__init__()
        """
        super().__init__()

        # The dongle handle
        self._led = blinkstick.find_first()
        if self._led is None:
            raise ValueError("No blinkstick found")

        # How we scale the blinkiness
        self._scale = math.pi * 0.5


    def _stop(self):
        """
        @see Notifier._stop()
        """
        super()._stop()
        self._led.set_color(red=0, green=0, blue=0)


    def _update(self, now, input_state, service_state, output_state):
        """
        @see PulsingNotifier._update()
        """
        # Unpack
        (i_since, i_mult, i_dir, i_velocity) = input_state
        (s_since, s_mult, s_dir, s_velocity) = service_state
        (o_since, o_mult, o_dir, o_velocity) = output_state

        # Pulse the other way if we're negative
        if i_velocity > 0:
            i_since =       (i_since % 1.0)
        else:
            i_since = 1.0 - (i_since % 1.0)
        if s_velocity > 0:
            s_since =       (s_since % 1.0)
        else:
            s_since = 1.0 - (s_since % 1.0)
        if o_velocity > 0:
            o_since =       (o_since % 1.0)
        else:
            o_since = 1.0 - (o_since % 1.0)

        # Mod at 1 and scale into radians
        i_theta = i_since * i_velocity * self._scale
        s_theta = s_since * s_velocity * self._scale
        o_theta = o_since * o_velocity * self._scale

        # Compute a level value from this
        i_level = 255 * (1 + math.sin(i_theta)) / 2
        s_level = 255 * (1 + math.sin(s_theta)) / 2
        o_level = 255 * (1 + math.sin(o_theta)) / 2

        # The RGB values
        r = int(max(0, min(255, o_level * o_mult)))
        g = int(max(0, min(255, s_level * s_mult)))
        b = int(max(0, min(255, i_level * i_mult)))

        # And set the value
        self._led.set_color(red=r, green=g, blue=b)
