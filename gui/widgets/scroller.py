from   kivy.clock            import Clock
from   kivy.lang             import Builder
from   kivy.properties       import StringProperty, NumericProperty
from   kivy.uix.effectwidget import EffectWidget
from   kivy.uix.scrollview   import ScrollView
from   threading             import Lock

import time

# ------------------------------------------------------------------------------

class Scroller(ScrollView):
    """
    A little scrolling pane to display messages.
    """
    # Age before we drop the text
    _MAX_AGE = 30
    _lock    = Lock()
    _lines   = []

    # The text to display
    text      = StringProperty ('', rebind=True)
    font_size = NumericProperty(20, rebind=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self._update, 0.1)


    def _update(self, *args):
        """
        Do housekeeping.
        """
        # Do all this under the lock so that we don't trip over other folks
        # adding things
        changed = False
        with self._lock:
            # Trim away any old lines
            limit = time.time()
            while len(self._lines) > 0 and self._lines[0][0] < limit:
                self._lines.pop(0)
                changed = True

            # And trim away any blank lines at the top
            while len(self._lines) > 0 and len(self._lines[0][1].strip()) == 0:
                self._lines.pop(0)
                changed = True

        # And update the text box if anything changed
        if changed:
            self._render()


    def set_text(self, text):
        # Nothing breeds nothing
        if not text:
            return

        # Do this under the lock so we don't triup over the timer
        with self._lock:
            # We timestamp all the lines so that we may decay them away
            expiry = time.time() + self._MAX_AGE

            # And set the lines and have them slowly decay away
            self._lines = []
            for line in text.split('\n'):
                if len(line.strip()) > 0:
                    self._lines.append((expiry, line))
                    expiry += 0.3

        # And update the text box
        self._render()


    def _render(self):
        """
        Render the lines into text.
        """
        # Do this under the lock so we don't trip over the timer
        with self._lock:
            self.text = '\n'.join(line for (now, line) in self._lines)
            self.scroll_y = 0.0

# ------------------------------------------------------------------------------

Builder.load_string("""
<Scroller>:
    do_scroll_x: True
    do_scroll_y: True

    Label:
        size_hint_y: None
        height: self.texture_size[1]
        font_name: 'FreeMonoBold'
        font_size: self.parent.font_size
        text_size: self.width * 0.9, None
        padding: 10, 10
        text: self.parent.text
        halign: 'center'
""")
