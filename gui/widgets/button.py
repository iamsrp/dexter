from kivy.lang       import Builder
from kivy.uix.button import Button

class StopButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._callback = None


    def set_callback(self, callback):
        """
        Set the function to be called when the button is pressed.
        """
        self._callback = callback


    def on_press(self, *args):
        if self._callback:
            self._callback()


Builder.load_string("""
<StopButton>:
    background_normal: 'stop.png'
    background_down:   'stop_pressed.png'
""")
