"""
A notifier which utilises the Pimoroni Scroll Hat Mini on a Raspberry Pi.

@see https://github.com/pimoroni/scroll-phat-hd.git
"""

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.notifier import ByComponentNotifier
from   threading       import Thread

import math
import scrollphathd
import time

# ------------------------------------------------------------------------------

class ScrollHatMiniNotifier(ByComponentNotifier):
    """
    A notifier for the Pimoroni Scroll HAT Mini.
    """
    def __init__(self, brightness=0.5):
        """
        @see ByComponentNotifier.__init__()

        :type  brightness: float
        :param brightness:
            How bright the display should be overall. A value between 0.0
            and 1.0.
        """
        super(ScrollHatMiniNotifier, self).__init__()

        # How bright do we want it?
        self._brightness = min(1.0, max(0.0, float(brightness)))

        # We need 3 sub-displays so we'll split up the display accordingly. We
        # make it use 3 squares, equally spaced. I luckily know that the the
        # display is 17x7 so that 'size' will evaluate to 5 and it means we can
        # have 3 5x5 sub-displays. We have a blank between each sub-display,
        # which neatly all adds up to 17 in width.
        w = (scrollphathd.DISPLAY_WIDTH - 2) // 3
        h =  scrollphathd.DISPLAY_HEIGHT
        self._size = min(w, h)

        # Figure out the centres of each display. We put the input in the middle
        # since it's the most commonly active one.
        w_step = self._size + 1
        self._service_off_x = 0 * w_step
        self._service_off_y = 1
        self._input_off_x   = 1 * w_step
        self._input_off_y   = 1
        self._output_off_x  = 2 * w_step
        self._output_off_y  = 1

        # The time, since epoch, when each component type stopped being active
        self._input_time   = 0
        self._service_time = 0
        self._output_time  = 0

        # The direction of the swirl
        self._input_dir   = 0
        self._service_dir = 0
        self._output_dir  = 0

        # The currently non-idle components
        self._inputs   = set()
        self._services = set()
        self._outputs  = set()


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
                if len(self._inputs) == 0:
                    self._input_time = 0
                    self._input_dir  = 0
            if self._is_service(component):
                if component in self._services:
                    self._services.remove(component)
                if len(self._services) == 0:
                    self._service_time = 0
                    self._service_dir  = 0
            if self._is_output(component):
                if component in self._outputs:
                    self._outputs.remove(component)
                if len(self._outputs) == 0:
                    self._output_time = 0
                    self._output_dir  = 0
        else:
            # Gone non-idle, add it to the appropriate group and reset the time
            if self._is_input(component):
                self._inputs.add(component)
                self._input_time = time.time()
                self._input_dir  = 1 if status is Notifier.ACTIVE else -1
            if self._is_service(component):
                self._services.add(component)
                self._service_time = time.time()
                self._service_dir  = 1 if status is Notifier.ACTIVE else -1
            if self._is_output(component):
                self._outputs.add(component)
                self._output_time = time.time()
                self._output_dir  = 1 if status is Notifier.ACTIVE else -1


    def _start(self):
        """
        @see Notifier._start()
        """
        # Turn it up etc.
        scrollphathd.set_brightness(self._brightness)

        # The thread which will maintain the display
        thread = Thread(name='ScrollHatUpdater', target=self._updater)
        thread.deamon = True
        thread.start()


    def _updater(self):
        """
        The method which will maintain the display.
        """
        # Some state variables
        i_mult = 0.0
        s_mult = 0.0
        o_mult = 0.0
        i_dir = 0.0
        s_dir = 0.0
        o_dir = 0.0

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

            # See what state we want these guys to be in. After 30s we figure
            # that the component is hung and turn it off.
            i_state = 1.0 if i_since < 30.0 else 0.0
            s_state = 1.0 if s_since < 30.0 else 0.0
            o_state = 1.0 if o_since < 30.0 else 0.0

            # Slide the multiplier and direction accordingly
            f = 0.2
            i_mult = (1.0 - f) * i_mult + f * i_state
            s_mult = (1.0 - f) * s_mult + f * s_state
            o_mult = (1.0 - f) * o_mult + f * o_state
            f = 0.01
            i_dir  = (1.0 - f) * i_dir  + f * self._input_dir
            s_dir  = (1.0 - f) * s_dir  + f * self._service_dir
            o_dir  = (1.0 - f) * o_dir  + f * self._output_dir

            # And actually update the display
            for y in range(self._size):
                for x in range(self._size):
                    # The pixel brightnesses, according to the pattern
                    i_v = self._pixel_value(x, y, i_since, i_dir)
                    s_v = self._pixel_value(x, y, s_since, s_dir)
                    o_v = self._pixel_value(x, y, o_since, o_dir)

                    i_x = self._input_off_x   + x
                    i_y = self._input_off_y   + y
                    s_x = self._service_off_x + x
                    s_y = self._service_off_y + y
                    o_x = self._output_off_x  + x
                    o_y = self._output_off_y  + y

                    # And set them
                    scrollphathd.pixel(i_x, i_y, i_v * i_mult)
                    scrollphathd.pixel(s_x, s_y, s_v * s_mult)
                    scrollphathd.pixel(o_x, o_y, o_v * o_mult)

            scrollphathd.show()

        # And we're done
        scrollphathd.clear()
        LOG.info("Stopped update thread")


    def _pixel_value(self, x, y, since, direction):
        """
        Get the intensity for the given coordinates at the given time index.
        """
        off = self._size // 2
        x -= off
        y -= off

        # Pulse a circle which is the full size of the sub-display
        dist = math.sqrt(pow(x, 2) + pow(y, 2)) / self._size
        return (direction * math.sin((dist - since) * 2 * math.pi) + 1.0) / 2.0
