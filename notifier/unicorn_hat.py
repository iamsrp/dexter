"""
Notifiers which utilise the Unicorn HATs on a Raspberry Pi.

@see https://github.com/pimoroni/unicornhatmini-python
@see https://github.com/pimoroni/unicorn-hat-hd
"""

from   datetime        import datetime
from   dexter.core     import Notifier
from   dexter.core.log import LOG
from   dexter.notifier import PulsingNotifier
from   threading       import Thread

import math
import time

# ------------------------------------------------------------------------------

class _Clockface():
    # The 3x5 digits
    _DIGITS = [
        [[ 1,1,1 ],
         [ 1,0,1 ],
         [ 1,0,1 ],
         [ 1,0,1 ],
         [ 1,1,1 ]],

         [[ 1,1,0 ],
          [ 0,1,0 ],
          [ 0,1,0 ],
          [ 0,1,0 ],
          [ 1,1,1 ]],

         [[ 1,1,1 ],
          [ 0,0,1 ],
          [ 1,1,1 ],
          [ 1,0,0 ],
          [ 1,1,1 ]],

         [[ 1,1,1 ],
          [ 0,0,1 ],
          [ 1,1,1 ],
          [ 0,0,1 ],
          [ 1,1,1 ]],

         [[ 1,0,1 ],
          [ 1,0,1 ],
          [ 1,1,1 ],
          [ 0,0,1 ],
          [ 0,0,1 ]],

         [[ 1,1,1 ],
          [ 1,0,0 ],
          [ 1,1,1 ],
          [ 0,0,1 ],
          [ 1,1,1 ]],

         [[ 1,1,1 ],
          [ 1,0,0 ],
          [ 1,1,1 ],
          [ 1,0,1 ],
          [ 1,1,1 ]],

         [[ 1,1,1 ],
          [ 0,0,1 ],
          [ 0,0,1 ],
          [ 0,0,1 ],
          [ 0,0,1 ]],

         [[ 1,1,1 ],
          [ 1,0,1 ],
          [ 1,1,1 ],
          [ 1,0,1 ],
          [ 1,1,1 ]],

         [[ 1,1,1 ],
          [ 1,0,1 ],
          [ 1,1,1 ],
          [ 0,0,1 ],
          [ 1,1,1 ]],
    ] 

    _EMPTY = \
         [[ 0,0,0 ],
          [ 0,0,0 ],
          [ 0,0,0 ],
          [ 0,0,0 ],
          [ 0,0,0 ]]

    _DIGIT_COL = [ 255, 255, 255 ]
    _COLON_COL = [ 128, 128, 128 ]
    

    def __init__(self, hrs, brightness):
        """
        :param hrs: 12 or 24 hour clock.
        """
        self._hrs        = int(hrs)
        self._brightness = max(0.0, min(1.0, float(brightness)))


    def render_hhmm(self, w, h, seconds):
        """
        Render the time into a WxH RGB buffer as an HH:MM image.
        
        :param seconds: Seconds since epoch.
        """
        def render(buf, num, x_off, y_off):
            # Pick the character to render
            if 0 <= num < len(self._DIGITS):
                digit = self._DIGITS[num]
            else:
                digit = self._EMPTY

            # Render it into the buffer.Note that the digits have reversed
            # indexing.
            value = [max(0, min(255, int(v * self._brightness)))
                     for v in self._DIGIT_COL]
            for y in range(len(digit)):
                for x in range(len(digit[y])):
                    buf_x = x + x_off
                    buf_y = y + y_off
                    if (0 <= buf_x < len(buf       ) and
                        0 <= buf_y < len(buf[buf_x]) and
                        digit[y][x]):
                        # We're in the buffer and the digit's pixel is set
                        buf[buf_x][buf_y] = value

        # Determine the digits' extents
        d_h = len(self._EMPTY)
        d_w = len(self._EMPTY[0])

        # Figure out the offsets of each digit in the time. Remember we need to
        # pad by one pixel horizontally.
        mid_x = w // 2
        mid_y = h // 2
        y_off = mid_y - d_h // 2
        h2_x_off = mid_x - d_w - 1
        h1_x_off = h2_x_off - d_w - 1
        m1_x_off = mid_x + 1
        m2_x_off = m1_x_off + d_w + 1

        # What we will render
        dt = datetime.fromtimestamp(int(seconds))

        # Create the buffer and render into it
        buf = [
            [
                [0, 0, 0] for _ in range(int(h))
            ] for _ in range(int(w))
        ]

        # Get the hours and minutes, special handling for 12hr clocks which go
        # from 1~12 twice, vs 24hr clocks which go from 00~23.
        hh = dt.hour
        if self._hrs == 12:
            if hh > 12:
                hh -= 12
            elif hh == 0:
                hh = 12
        mm = dt.minute

        # Draw the digits
        if hh >= 10:
            render(buf, int(hh / 10), h1_x_off, y_off)
        render(buf, int(hh % 10), h2_x_off, y_off)
        render(buf, int(mm / 10), m1_x_off, y_off)
        render(buf, int(mm % 10), m2_x_off, y_off)

        # Finally, put in the colon, if we're on an odd second bonundary (so it
        # flashes)
        if (int(seconds) & 1) == 1:
            value = [max(0, min(255, int(self._brightness * v)))
                     for v in self._COLON_COL]
            buf[mid_x    ][mid_y - 1] = value
            buf[mid_x    ][mid_y + 1] = value
            buf[mid_x - 1][mid_y - 1] = value
            buf[mid_x - 1][mid_y + 1] = value

        # And give it back
        return buf


class _UnicornHatNotifier(PulsingNotifier):
    """
    A notifier for the Unicorn HAT family from Pimoroni.
    """
    def __init__(self,
                 brightness,
                 clock_type,
                 clock_brightness,
                 rotation,
                 flip_x,
                 flip_y):
        """
        @see ByComponentNotifier.__init__()

        :param brightness:       From 0.0 to 1.0.
        :param clock_type:       The type of clock to display, one of ``12``,
                                 ``24``, or ``None``.
        :param clock_brightness: From 0.0 to 1.0.
        :param rotation:         Rotate the display by ``0``, ``90``, ``180``,
                                 or ``270`` degrees.
        :param flip_x:           Whether to flip the horizontal rendering.
        :param flip_y:           Whether to flip the vertical rendering.
        """
        super().__init__()

        # Save params
        self._start_brightness = float(brightness)
        self._rotation         = int(rotation / 90)
        self._flip_x           = bool(flip_x)
        self._flip_y           = bool(flip_y)

        # How we render the clock
        if clock_type is None:
            self._clockface = None
        elif clock_type not in (12, "12", 24, "24"):
            raise ValueError("Bad clock type")
        else:
            self._clockface = _Clockface(clock_type,
                                         float(clock_brightness))


    def set_brightness(self, brightness):
        """
        Set the brightness, this should be a value in the range ``[0.0, 1.0]``.
        """
        self._brightness(max(0.0, min(1.0, brightness)))


    def _start(self):
        """
        @see Notifier._start()
        """
        super()._start()

        # How we like it
        self._brightness(self._start_brightness)


    def _stop(self):
        """
        @see Notifier._stop()
        """
        super()._stop()
        self._off()


    def _update(self, now, input_state, service_state, output_state):
        """
        @see PulsingNotifier._update()
        """
        # Unpack
        (i_since, i_mult, i_dir, i_velocity) = input_state
        (s_since, s_mult, s_dir, s_velocity) = service_state
        (o_since, o_mult, o_dir, o_velocity) = output_state

        # We need to know these for later
        (w, h) = self._get_shape()
        mid_w  = w / 2
        mid_h  = h / 2

        # Render the clockface into a buffer to use, maybe
        if self._clockface is not None:
            clock = self._clockface.render_hhmm(w, h, now)
        else:
            clock = None

        # Compute an index value from this
        index_scale = 100
        i_index = int(i_since * index_scale)
        s_index = int(s_since * index_scale)
        o_index = int(o_since * index_scale)

        # And actually update the display
        for y in range(h):
            for x in range(w):
                # Swirl expects the values to be relative to a centred
                # origin of 0,0
                rx = x - mid_w
                ry = y - mid_h

                # The pixel brightnesses, according to the pattern
                i_s = self._swirl(rx, ry, i_index, i_velocity)
                s_s = self._swirl(rx, ry, s_index, s_velocity)
                o_s = self._swirl(rx, ry, o_index, o_velocity)

                # The RGB values
                r = o_s * o_mult
                g = s_s * s_mult
                b = i_s * i_mult

                # Merge in the clock, if any
                if clock is not None:
                    r += clock[x][y][0]
                    g += clock[x][y][1]
                    b += clock[x][y][2]

                # And set them
                self._set_pixel(
                    x,
                    y,
                    int(max(0, min(255, r))),
                    int(max(0, min(255, g))),
                    int(max(0, min(255, b)))
                )

        self._show()


    def _brightness(self, brightness):
        """
        Set the brightness to a value in the range ``[0.0, 1.0]``.
        """
        raise NotImplementedError("Abstract method called")


    def _get_shape(self):
        """
        Get the width and height of the display, as a tuple, adjusting by any global
        mutation parameters.
        """
        # Get the shape, handling any rotation
        (w, h) = self._get_shape_raw()
        if self._rotation == 1 or self._rotation == 3:
            return (h, w)
        else:
            return (w, h)


    def _get_shape_raw(self):
        """
        Get the width and height of the display, as a tuple.
        """
        raise NotImplementedError("Abstract method called")


    def _set_pixel(self, x, y, r, g, b):
        """
        Set the pixel at ``(x,y)`` to the given ``(r,g,b)`` value, adjusting by any
        global mutation parameters.
        """
        # Need to know the raw shape
        (w, h) = self._get_shape_raw()

        # Handle horizontal flipping
        if self._flip_x:
            x = w - x - 1
        if self._flip_y:
            y = h - y - 1

        # And any rotation
        if   self._rotation == 1:
            raw_x = w - y - 1
            raw_y = x
        elif self._rotation == 2:
            raw_x = w - x - 1
            raw_y = h - y - 1
        elif self._rotation == 3:
            raw_x = y
            raw_y = h - x - 1
        else:
            raw_x = x
            raw_y = y

        self._set_pixel_raw(raw_x, raw_y, r, g, b)


    def _set_pixel_raw(self, x, y, r, g, b):
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
    def __init__(self,
                 brightness      =0.75,
                 clock_type      =24,
                 clock_brightness=0.5,
                 rotation        =90,
                 flip_x          =True,
                 flip_y          =False):
        """
        @see _UnicornHatNotifier.__init__()
        """
        super().__init__(brightness      =brightness,
                         clock_type      =clock_type,
                         clock_brightness=clock_brightness,
                         rotation        =rotation,
                         flip_x          =flip_x,
                         flip_y          =flip_y)

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


    def _get_shape_raw(self):
        """
        @see _UnicornHatNotifier._get_shape_raw
        """
        return self._hat.get_shape()


    def _set_pixel_raw(self, x, y, r, g, b):
        """
        @see _UnicornHatNotifier._set_pixel_raw
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
    def __init__(self,
                 brightness      =0.5,
                 clock_type      =24,
                 clock_brightness=0.5,
                 rotation        =180,
                 flip_x          =False,
                 flip_y          =False):
        """
        @see _UnicornHatNotifier.__init__()
        """
        super().__init__(brightness      =brightness,
                         clock_type      =clock_type,
                         clock_brightness=clock_brightness,
                         rotation        =rotation,
                         flip_x          =flip_x,
                         flip_y          =flip_y)

        from unicornhatmini import UnicornHATMini
        self._hat = UnicornHATMini()


    def _brightness(self, brightness):
        """
        @see _UnicornHatNotifier._brightness
        """
        self._hat.set_brightness(brightness)


    def _get_shape_raw(self):
        """
        @see _UnicornHatNotifier._get_shape_raw
        """
        return self._hat.get_shape()


    def _set_pixel_raw(self, x, y, r, g, b):
        """
        @see _UnicornHatNotifier._set_pixel_raw
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
