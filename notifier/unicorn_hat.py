"""
Notifiers which utilise the Unicorn HATs on a Raspberry Pi.

@see https://github.com/pimoroni/unicornhatmini-python
@see https://github.com/pimoroni/unicorn-hat-hd
"""

from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.notifier import ByComponentNotifier
from   threading       import Thread

import math
import time

# ------------------------------------------------------------------------------

class _UnicornHatNotifier(ByComponentNotifier):
    """
    A notifier for the Unicorn HAT family from Pimoroni.
    """
    def __init__(self, brightness):
        """
        @see ByComponentNotifier.__init__()
        """
        super(_UnicornHatNotifier, self).__init__()

        # Used when we start
        self._start_brightness = brightness

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


    def set_brightness(self, brightness):
        """
        Set the brightness, this should be a value in the range ``[0.0, 1.0]``.
        """
        self._brightness(max(0.0, min(1.0, brightness)))


    def _start(self):
        """
        @see Notifier._start()
        """
        # Set things up
        self._brightness(self._start_brightness)

        # The thread which will maintain the display
        thread = Thread(target=self._updater)
        thread.deamon = True
        thread.start()


    def _get_shape(self):
        """
        Get the width and height of the display, as a tuple.
        """
        raise NotImplementedError("Abstract method called")


    def _brightness(self, brightness):
        """
        Set the brightness to a value in the range ``[0.0, 1.0]``.
        """
        raise NotImplementedError("Abstract method called")


    def _rotation(self, rotation):
        """
        Set the rotation, to one of: ``0``, ``90``, ``180``, ``270``
        """
        raise NotImplementedError("Abstract method called")


    def _set_pixel(self, x, y, r, g, b):
        """
        Set the pixel at ``(x,y)`` to the given ``(r,g,b)`` value.
        """
        raise NotImplementedError("Abstract method called")


    def _show(self):
        """
        Show the display.
        """
        raise NotImplementedError("Abstract method called")


    def _off(self):
        """
        Turn off the display.
        """
        raise NotImplementedError("Abstract method called")


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

        # We need to know these for later
        (w, h) = self._get_shape()
        mid_w  = w / 2
        mid_h  = h / 2

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

            # Compute an index value from this
            index_scale = 100
            i_index = int(i_since * index_scale)
            s_index = int(s_since * index_scale)
            o_index = int(o_since * index_scale)

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
            for y in range(h):
                for x in range(w):
                    # Swirl expects the values to be relative to a centred
                    # origin of 0,0
                    rx = x - mid_w
                    ry = y - mid_h

                    # The pixel brightnesses, according to the pattern
                    i_s = self._swirl(rx, ry, i_index, i_dir)
                    s_s = self._swirl(rx, ry, s_index, s_dir)
                    o_s = self._swirl(rx, ry, o_index, o_dir)

                    # The RGB values
                    r = int(max(0, min(255, o_s * o_mult)))
                    g = int(max(0, min(255, s_s * s_mult)))
                    b = int(max(0, min(255, i_s * i_mult)))

                    # And set them
                    self._set_pixel(x, y, r, g, b)

            self._show()

        # And we're done
        self._off()
        LOG.info("Stopped update thread")


    def _swirl(self, x, y, index, direction):
        """
        Get the intensity for the given coordinates, centered at (0,0), at the given
        time index.

        Adapted from the HD HAT example code in::
            https://github.com/pimoroni/unicorn-hat-hd
        """
        dist  = math.sqrt(pow(x, 2) + pow(y, 2)) / 2.0
        angle = (direction * index / 10.0) + (dist * 1.5)

        s = math.sin(angle);
        c = math.cos(angle);

        xs = x * c - y * s;
        ys = x * s + y * c;

        r = abs(xs + ys)
        r *= 12.0
        r -= 20

        return r


class UnicornHatHdNotifier(_UnicornHatNotifier):
    """
    A notifier for the Unicorn HAT HD.
    """
    def __init__(self, brightness=0.5):
        """
        @see _UnicornHatNotifier.__init__()
        """
        super(UnicornHatHdNotifier, self).__init__(brightness=brightness)

        import unicornhathd
        self._hat = unicornhathd


    def _brightness(self, brightness):
        """
        @see _UnicornHatNotifier._brightness
        """
        # This is inconsistently named between the github and pip versions
        if hasattr(self._hat, "set_brightness"):
            self._hat.set_brightness(brightness)
        elif hasattr(self._hat, "brightness"):
            self._hat.brightness(brightness)


    def _rotation(self, rotation):
        """
        @see _UnicornHatNotifier._rotation
        """
        self._hat.set_rotation(rotation)


    def _get_shape(self):
        """
        @see _UnicornHatNotifier._get_shape
        """
        return self._hat.get_shape()


    def _set_pixel(self, x, y, r, g, b):
        """
        @see _UnicornHatNotifier._set_pixel
        """
        self._hat.set_pixel(x, y, r, g, b)


    def _show(self):
        """
        @see _UnicornHatNotifier._show
        """
        self._hat.show()


    def _off(self):
        """
        @see _UnicornHatNotifier._off
        """
        self._hat.off()


class UnicornHatMiniNotifier(_UnicornHatNotifier):
    """
    A notifier for the Unicorn HAT Mini.
    """
    def __init__(self, brightness=0.5):
        """
        @see _UnicornHatNotifier.__init__()
        """
        super(UnicornHatMiniNotifier, self).__init__(brightness=brightness)

        from unicornhatmini import UnicornHATMini
        self._hat = UnicornHATMini()


    def _brightness(self, brightness):
        """
        @see _UnicornHatNotifier._brightness
        """
        self._hat.set_brightness(brightness)


    def _rotation(self, rotation):
        """
        @see _UnicornHatNotifier._rotation
        """
        self._hat.set_rotation(rotation)


    def _get_shape(self):
        """
        @see _UnicornHatNotifier._get_shape
        """
        return self._hat.get_shape()


    def _set_pixel(self, x, y, r, g, b):
        """
        @see _UnicornHatNotifier._set_pixel
        """
        self._hat.set_pixel(x, y, r, g, b)


    def _show(self):
        """
        @see _UnicornHatNotifier._show
        """
        self._hat.show()


    def _off(self):
        """
        @see _UnicornHatNotifier._off
        """
        self._hat.clear()
        self._hat.show()
