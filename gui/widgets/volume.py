from dexter.core.audio     import MIN_VOLUME, MAX_VOLUME, get_volume, set_volume
from kivy.clock            import Clock
from kivy.lang             import Builder
from kivy.properties       import NumericProperty
from kivy.uix.slider       import Slider


class Volume(Slider):
    MIN_VOL = MIN_VOLUME
    MAX_VOL = MAX_VOLUME

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self._update, 0.2)


    def _update(self, *args):
            vol = get_volume()
            if self.value != vol:
                self.value = vol


    def on_value(self, *args):
        try:
            set_volume(self.value)
        except ValueError as e:
            LOG.error("Failed to set volume to %d: %s", self.value, e)


Builder.load_string("""
<Volume>:
    min:  root.MIN_VOL
    max:  root.MAX_VOL
    step: 1
""")
