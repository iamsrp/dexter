from dexter.gui.widgets.button     import StopButton
from dexter.gui.widgets.background import Background
from dexter.gui.widgets.clock      import MainClock
from dexter.gui.widgets.scroller   import Scroller
from dexter.gui.widgets.volume     import Volume
from kivy.lang                     import Builder
from kivy.properties               import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.floatlayout          import FloatLayout

class MainScreen(FloatLayout):
    """
    The class for Dexter's main screen.

    This is mostly configured to run with the standard ``800x600`` screen
    size. If you want to run with something different then tweak the scaling
    values in the GUI configuration.
    """
    # Widgets which we need access to
    inputs_widget   = ObjectProperty(None)
    outputs_widget  = ObjectProperty(None)
    scroller_widget = ObjectProperty(None)
    services_widget = ObjectProperty(None)
    stop_widget     = ObjectProperty(None)
    volume_widget   = ObjectProperty(None)

    # Configuration
    scale         = NumericProperty(1.0,   rebind=True)
    message_scale = NumericProperty(1.0,   rebind=True)
    clock_scale   = NumericProperty(1.0,   rebind=True)
    clock_fmt     = StringProperty ('24h', rebind=True)

    def __init__(self,
                 scale,
                 message_scale,
                 clock_scale,
                 clock_format):
        """
        CTOR

        :param scale:
            The overall scaling for the GUI.
        :param message_scale:
            The scaling for the message window.
        :param clock_scale:
            The scaling for the clock.
        :param clock_format:
            The clock format, either ``12h`` or ``24h``.
        """
        super().__init__()
        self.scale         = scale
        self.message_scale = message_scale
        self.clock_scale   = clock_scale
        self.clock_format  = clock_format


Builder.load_string("""
<MainScreen>
    scroller_widget: scroller
    stop_widget:     stop
    volume_widget:   volume
    inputs_widget:   inputs
    outputs_widget:  outputs
    services_widget: services

    BoxLayout:
        BoxLayout:
            orientation: 'vertical'
            halign:      'center'
            size_hint_x: 0.8
            padding:     5
            spacing:     5

            BoxLayout:
                size_hint_y: 0.2 * root.scale * root.clock_scale
                MainClock:
                    font_size: 60 * root.scale * root.clock_scale
                    format:    root.clock_fmt
                    bold:      True
                    halign:    'center'
                    valign:    'top'

            Volume:
                id: volume
                valign:      'top'
                size_hint_y: 0.1 * root.scale
                orientation: 'horizontal'

            BoxLayout:
                size_hint_y: 0.1
                Label:
                    id:        inputs
                    font_size: 30 * root.scale
                    bold:      True
                    halign:    'center'
                Label:
                    id:        services
                    font_size: 30 * root.scale
                    bold:      True
                    halign:    'center'
                Label:
                    id:        outputs
                    font_size: 30 * root.scale
                    bold:      True
                    halign:    'center'

            Scroller:
                id:          scroller
                pos_hint:    { 'center_x' : 0.5 }
                size_hint_y: 0.8
                font_size:   25 * root.scale * root.message_scale
                halign:      'center'

            BoxLayout:
                pos_hint:    { 'center_x' : .5 }
                size_hint_x: 0.17
                size_hint_y: 0.3

                StopButton:
                    id:     stop
                    halign: 'right'
""")
