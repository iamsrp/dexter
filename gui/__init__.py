from   dexter.core          import Notifier
from   dexter.core.log      import LOG
from   dexter.gui.screens   import MainScreen
from   dexter.input         import Input, Token
from   dexter.notifier      import ByComponentNotifier
from   dexter.output        import Output
from   kivy.app             import App
from   kivy.clock           import Clock

import kivy
import math
import os
import time

# ------------------------------------------------------------------------------

class DexterGui(App):
    """
    The GUI front-end for Dexter.
    """
    def __init__(self,
                 dexter,
                 scale        =1.0,
                 message_scale=1.0,
                 clock_scale  =1.0,
                 clock_format='24h'):
        """
        Standard CTOR.

        :param dexter: The `Dexter` instance.
        """
        super().__init__()
        self._scale         = float(scale)
        self._message_scale = float(message_scale)
        self._clock_scale   = float(clock_scale)
        self._clock_format  = str(clock_format).lower()


        # Our GUI components which we need to care about
        self._main            = None
        self._inputs_widget   = None
        self._outputs_widget  = None
        self._scroller_widget = None
        self._services_widget = None
        self._stop_widget     = None
        self._volume_widget   = None

        # Needed for building components
        state = dexter.state

        # The way we send messages to the Dexter system
        self._input = _GuiInput(state, dexter.key_phrases[0])

        # Our Dexter components
        self._inputs    = [ self._input ]
        self._outputs   = [ _GuiOutput(state, self) ]
        self._notifiers = [ _GuiNotifier(self)      ]

        # Ensure we know where our images live
        kivy.resources.resource_add_path(
            os.path.join(
                os.path.abspath(os.path.dirname(__file__)), 'images'
            )
        )


    def build(self):
        """
        Create the display.
        """
        # Build and fail fast whe yanking out widgets
        self._main            = MainScreen(self._scale,
                                           self._message_scale,
                                           self._clock_scale,
                                           self._clock_format)
        self._inputs_widget   = self._main.inputs_widget
        self._outputs_widget  = self._main.outputs_widget
        self._scroller_widget = self._main.scroller_widget
        self._services_widget = self._main.services_widget
        self._stop_widget     = self._main.stop_widget
        self._volume_widget   = self._main.volume_widget

        # Bind the stop button
        self._stop_widget.set_callback(self._stop)

        return self._main


    def get_inputs(self):
        """
        Get the set of input components which the UI provides, if any.
        """
        return self._inputs


    def get_outputs(self):
        """
        Get the set of output components which the UI provides, if any.
        """
        return self._outputs


    def get_notifiers(self):
        """
        Get the set of notifier components which the UI provides, if any.
        """
        return self._notifiers


    @property
    def scroller(self):
        return self._scroller_widget


    def set_inputs_text(self, text):
        """
        Set the text of the inputs widget.
        """
        self._inputs_widget.text = text


    def set_inputs_color(self, color):
        """
        Set the text color of the inputs widget.
        """
        self._inputs_widget.color = color


    def set_outputs_text(self, text):
        """
        Set the text of the outputs widget.
        """
        self._outputs_widget.text = text


    def set_outputs_color(self, color):
        """
        Set the text color of the outputs widget.
        """
        self._outputs_widget.color = color


    def set_services_text(self, text):
        """
        Set the text of the services widget.
        """
        self._services_widget.text = text


    def set_services_color(self, color):
        """
        Set the text color of the services widget.
        """
        self._services_widget.color = color


    def _stop(self):
        """
        Called when the stop button is pressed.
        """
        self._input.write("stop")


class _GuiInput(Input):
    """
    An input which gets the input from the GUI.
    """
    def __init__(self, state, key_pharse):
        """
        @see Input.__init__()

        :param key_pharse: The Dexter key-pharse to prefix.
        """
        super().__init__(state)

        self._prefix = [Token(word.strip(), 1.0, True)
                        for word in str(key_pharse).strip().split()
                        if word]

        self._input = []


    def write(self, text):
        """
        Write some text to the input.
        """
        if text:
            self._input.append(
                self._prefix +
                [Token(word.strip(), 1.0, True)
                 for word in str(text).strip().split()
                 if word]
            )


    def read(self):
        """
        @see Input.read
        """
        if len(self._input) > 0:
            try:
                return self._input.pop(0)
            except:
                pass



class _GuiOutput(Output):
    """
    An output which sends the output into the GUI.
    """
    def __init__(self, state, gui):
        """
        @see Output.__init__()
        """
        super().__init__(state)
        self._gui = gui


    def write(self, text):
        """
        @see Output.write
        """
        self._gui.scroller.set_text(text)


class _GuiNotifier(ByComponentNotifier):
    """
    A notifier which sets the status in the widgets
    """
    def __init__(self, gui):
        super().__init__()
        self._gui = gui

        self._inputs_since   = 0
        self._outputs_since  = 0
        self._services_since = 0


    def update_status(self, component, status):
        """
        @see Notifier.update_status()
        """
        # Ignore junk
        if component is None or status is None:
            return

        if status is Notifier.IDLE:
            if   self._is_input(component):
                self._gui.set_inputs_text('')
                Clock.unschedule(self._pulse_inputs)
            elif self._is_output(component):
                self._gui.set_outputs_text('')
                Clock.unschedule(self._pulse_outputs)
            elif self._is_service(component):
                self._gui.set_services_text('')
                Clock.unschedule(self._pulse_services)
        else:
            if   self._is_input(component):
                self._gui.set_inputs_text('LISTENING')
                self._inputs_since = time.time()
                Clock.schedule_interval(self._pulse_inputs, 0.1)
            elif self._is_output(component):
                self._gui.set_outputs_text('SPEAKING')
                self._outputs_since = time.time()
                Clock.schedule_interval(self._pulse_outputs, 0.1)
            elif self._is_service(component):
                self._gui.set_services_text('WORKING')
                self._services_since = time.time()
                Clock.schedule_interval(self._pulse_services, 0.1)


    def _pulse_inputs(self, *args):
        """
        Pulse the input text.
        """
        since = time.time() - self._inputs_since
        v = min(1.0, max(0.0, (math.sin(since * math.pi) + 2) / 3))
        self._gui.set_inputs_color((v, v, v, v))


    def _pulse_outputs(self, *args):
        """
        Pulse the input text.
        """
        since = time.time() - self._outputs_since
        v = min(1.0, max(0.0, (math.sin(since * math.pi) + 2) / 3))
        self._gui.set_outputs_color((v, v, v, v))


    def _pulse_services(self, *args):
        """
        Pulse the input text.
        """
        since = time.time() - self._services_since
        v = min(1.0, max(0.0, (math.sin(since * math.pi) + 2) / 3))
        self._gui.set_services_color((v, v, v, v))
