"""
Notifiers which utilise the Adafruit DotStar LEDs.
"""

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.notifier import ByComponentNotifier
from   threading       import Thread

import adafruit_dotstar
import board
import math
import time

# ------------------------------------------------------------------------------

class VoiceBonnetNotifier(ByComponentNotifier):
    """
    A notifier for the Blink1 USB dongle.
    """
    _DOTSTAR_DATA  = board.D5
    _DOTSTAR_CLOCK = board.D6
    
    def __init__(self,
                 brightness=0.2):
        """
        @see ByComponentNotifier.__init__()
        :type  brightness: float
        :param brightness:
            The dots' LED brightness.
        """
        super(VoiceBonnetNotifier, self).__init__()

        # The time, since epoch, when each component type stopped being active
        self._input_time   = 0
        self._service_time = 0
        self._output_time  = 0

        # The currently non-idle components
        self._inputs   = set()
        self._services = set()
        self._outputs  = set()

        # The handle on the dots
        self._dots = adafruit_dotstar.DotStar(self._DOTSTAR_CLOCK,
                                              self._DOTSTAR_DATA,
                                              3,
                                              brightness=brightness)


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
            if self._is_service(component):
                if component in self._services:
                    self._services.remove(component)
                if len(self._services) == 0:
                    self._service_time  = 0
            if self._is_output(component):
                if component in self._outputs:
                    self._outputs.remove(component)
                if len(self._outputs)  == 0:
                    self._output_time   = 0

        else:
            # Gone non-idle, add it to the appropriate group and reset the time
            if self._is_input(component):
                self._inputs.add(component)
                self._input_time   = time.time()
            if self._is_service(component):
                self._services.add(component)
                self._service_time = time.time()
            if self._is_output(component):
                self._outputs.add(component)
                self._output_time  = time.time()


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
        for i in range(self._dots.n):
            self._dots[i] = (0, 0, 0)


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
            i_since = now - self._input_time
            s_since = now - self._service_time
            o_since = now - self._output_time

            # Compute an level value from this
            level_scale = math.pi * 2
            i_level = 255 * (1 + math.sin(i_since * level_scale)) / 2
            s_level = 255 * (1 + math.sin(s_since * level_scale)) / 2
            o_level = 255 * (1 + math.sin(o_since * level_scale)) / 2

            # See what state we want these guys to be in. After 30s we figure
            # that the component is hung and turn it off.
            i_state = 1.0 if i_since < 30.0 else 0.0
            s_state = 1.0 if s_since < 30.0 else 0.0
            o_state = 1.0 if o_since < 30.0 else 0.0

            # Slide the multiplier accordingly
            f = 0.1
            i_mult = (1.0 - f) * i_mult + f * i_state
            s_mult = (1.0 - f) * s_mult + f * s_state
            o_mult = (1.0 - f) * o_mult + f * o_state

            # The RGB values
            r = int(max(0, min(255, o_level * o_mult)))
            g = int(max(0, min(255, s_level * s_mult)))
            b = int(max(0, min(255, i_level * i_mult)))

            # And set the dots
            for i in range(self._dots.n):
                new = [r, g, b, 1.0]
                if self._dots[i] != new:
                    self._dots[i] = new
            self._dots.show()

        # And we're done
        for i in range(self._dots.n):
            self._dots[i] = (0, 0, 0)
        LOG.info("Stopped update thread")
