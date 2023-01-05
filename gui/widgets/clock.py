from kivy.properties import StringProperty
from kivy.clock      import Clock
from kivy.uix.label  import Label

import time

# ----------------------------------------------------------------------

class MainClock(Label):
    format = StringProperty('24h')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self.update_clock, 0.1)


    def update_clock(self, *args):
        if self.format == '12h':
            fmt = '%r'
        elif self.format == '24h':
            fmt = '%T'
        else:
            raise ValueError("Bad time format '%s'" % self.format)
        self.text = time.strftime(fmt, time.localtime(time.time()))
