"""
Notifiers which utilise the thingm Blink1 USB dongle.

To make it work you will need to make it accessible. This is best done using
their udev file (see the instructions in it)::
   https://raw.githubusercontent.com/todbot/blink1/main/linux/51-blink1.rules

I've seen this dongle misbehaving on some machines.

@see http://blink1.thingm.com/libraries/
"""

from   blink1.blink1   import Blink1
from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.notifier import PulsingNotifier
from   threading       import Thread

import math
import time

# ------------------------------------------------------------------------------

class Blink1Notifier(PulsingNotifier):
    """
    A notifier for the Blink1 USB dongle.
    """
    def __init__(self):
        """
        @see PulsingNotifier.__init__()
        """
        super().__init__()

        # The dongle handle
        self._b1 = Blink1()

        # How we scale the blinkiness
        self._scale = math.pi * 0.5


    def _stop(self):
        """
        @see Notifier._stop()
        """
        super()._stop()
        self._b1.fade_to_rgb(0, 0, 0, 0)


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
        i_theta = i_since * abs(i_velocity) * self._scale
        s_theta = s_since * abs(s_velocity) * self._scale
        o_theta = o_since * abs(o_velocity) * self._scale

        # Compute a level value from this
        i_level = 255 * (1 + math.sin(i_theta)) / 2
        s_level = 255 * (1 + math.sin(s_theta)) / 2
        o_level = 255 * (1 + math.sin(o_theta)) / 2

        # The RGB values
        r = int(max(0, min(255, o_level * o_mult)))
        g = int(max(0, min(255, s_level * s_mult)))
        b = int(max(0, min(255, i_level * i_mult)))

        # And set the value, instantaniously
        self._b1.fade_to_rgb(0, r, g, b)
