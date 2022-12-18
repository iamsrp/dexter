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
from   dexter.notifier import ByComponentNotifier
from   threading       import Thread

import math
import time

# ------------------------------------------------------------------------------

class Blink1Notifier(ByComponentNotifier):
    """
    A notifier for the Blink1 USB dongle.
    """
    def __init__(self):
        """
        @see ByComponentNotifier.__init__()
        """
        super(Blink1Notifier, self).__init__()

        # The time, since epoch, when each component type stopped being active
        self._input_time   = 0
        self._service_time = 0
        self._output_time  = 0

        # The direction of motion
        self._input_dir   = 0
        self._service_dir = 0
        self._output_dir  = 0

        # The currently non-idle components
        self._inputs   = set()
        self._services = set()
        self._outputs  = set()

        # The actual dongle handle
        self._b1 = Blink1()


    def update_status(self, component, status):
        """
        @see Notifier.update_status()
        """
        # Sanity
        if component is None or status is None:
            return

        # See if the component has become idle or not
        if status is Notifier.IDLE:
            # Gone idle, remove it from the appropriate group. If that group
            # goes empty then wipe out the time.
            if self._is_input(component):
                if component in self._inputs:
                    self._inputs.remove(component)
                if len(self._inputs)   == 0:
                    self._input_time    = 0
                    self._input_dir     = 0
            if self._is_service(component):
                if component in self._services:
                    self._services.remove(component)
                if len(self._services) == 0:
                    self._service_time  = 0
                    self._service_dir   = 0
            if self._is_output(component):
                if component in self._outputs:
                    self._outputs.remove(component)
                if len(self._outputs)  == 0:
                    self._output_time   = 0
                    self._output_dir    = 0

        else:
            # Gone non-idle, add it to the appropriate group and reset the time
            if self._is_input(component):
                self._inputs.add(component)
                self._input_time   = time.time()
                self._input_dir    = 1 if status is Notifier.ACTIVE else -1
            if self._is_service(component):
                self._services.add(component)
                self._service_time = time.time()
                self._service_dir  = 1 if status is Notifier.ACTIVE else -1
            if self._is_output(component):
                self._outputs.add(component)
                self._output_time  = time.time()
                self._output_dir   = 1 if status is Notifier.ACTIVE else -1


    def _start(self):
        """
        @see Notifier._start()
        """
        # The thread which will maintain the display
        thread = Thread(target=self._updater)
        thread.deamon = True
        thread.start()


    def _stop(self):
        """
        @see Notifier._stop()
        """
        self._b1.fade_to_rgb(0, 0, 0, 0)


    def _updater(self):
        """
        The method which will update the dongle.
        """
        # Some state variables
        i_mult = 0.0
        s_mult = 0.0
        o_mult = 0.0

        # And off we go!
        LOG.info("Started update thread")
        while self.is_running:
            # Don't busy-wait
            time.sleep(0.01)

            # What time is love?
            now = time.time()

            # How long since these components went non-idle
            i_since = (now - self._input_time  ) % 1.0
            s_since = (now - self._service_time) % 1.0
            o_since = (now - self._output_time ) % 1.0
            if self._input_dir < 0:
                i_since = 1.0 - i_since
            if self._service_dir < 0:
                s_since = 1.0 - s_since
            if self._output_dir < 0:
                o_since = 1.0 - o_since

            # Compute an level value from this
            level_scale = math.pi * 0.5
            i_level = 255 * (1 + math.sin(i_since * level_scale)) / 2
            s_level = 255 * (1 + math.sin(s_since * level_scale)) / 2
            o_level = 255 * (1 + math.sin(o_since * level_scale)) / 2

            # See what state we want these guys to be in. After 30s we figure
            # that the component is hung and turn it off.
            i_state = abs(self._input_dir  ) if i_since < 30.0 else 0.0
            s_state = abs(self._service_dir) if s_since < 30.0 else 0.0
            o_state = abs(self._output_dir ) if o_since < 30.0 else 0.0

            # Slide the multiplier accordingly
            f = 0.1
            i_mult = (1.0 - f) * i_mult + f * i_state
            s_mult = (1.0 - f) * s_mult + f * s_state
            o_mult = (1.0 - f) * o_mult + f * o_state

            # The RGB values
            r = int(max(0, min(255, o_level * o_mult)))
            g = int(max(0, min(255, s_level * s_mult)))
            b = int(max(0, min(255, i_level * i_mult)))

            # And set the value, instantaniously
            self._b1.fade_to_rgb(0, r, g, b)

        # And we're done
        self._b1.fade_to_rgb(0, 0, 0, 0)
        LOG.info("Stopped update thread")
