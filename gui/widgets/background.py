from kivy.lang             import Builder
from kivy.properties       import StringProperty, NumericProperty, ListProperty
from kivy.uix.effectwidget import EffectWidget


class Background(EffectWidget):
    uri       = StringProperty(None, allownone=True)
    default   = StringProperty()
    blur_size = NumericProperty(64)
    outbounds = NumericProperty(0)


Builder.load_string("""
#:import HBlur kivy.uix.effectwidget.HorizontalBlurEffect
#:import VBlur kivy.uix.effectwidget.VerticalBlurEffect
#:import Window kivy.core.window.Window

<Background>
    effects: (HBlur(size=10), VBlur(size=10), HBlur(size=self.blur_size), VBlur(size=self.blur_size))
    size_hint: (1 + root.outbounds, 1 + root.outbounds)
    x: - Window.width  * root.outbounds/2.0
    y: - Window.height * root.outbounds/2.0
""")
