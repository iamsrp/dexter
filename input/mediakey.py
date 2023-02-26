"""
An input which uses the Media Keys via dbus.
"""

from   dexter.input       import Input, Token
from   dexter.core.log    import LOG
from   dbus.mainloop.glib import DBusGMainLoop
from   gi.repository      import GLib
from   threading          import Thread

import dbus

# ------------------------------------------------------------------------------

class MediaKeyInput(Input):
    """
    A way to get input from the media keys.
    """
    _APP = 'Dexter'

    def __init__(self,
                 state,
                 prefix  ='Dexter',
                 play_key='play or pause',
                 stop_key='stop',
                 next_key='next song',
                 prev_key='previous song'):
        """
        @see Input.__init__()
        :type  prefix: str
        :param prefix:
            The prefix to use when sending the inputs.
        :type  play_key: str
        :param play_key:
            What string to send when the Play key is pressed.
        :type  stop_key: str
        :param stop_key:
            What string to send when the Stop key is pressed.
        :type  next_key: str
        :param next_key:
            What string to send when the Next key is pressed.
        :type  prev_key: str
        :param prev_key:
            What string to send when the Previous key is pressed.
        """
        super().__init__(state)

        def tokenize(string):
            if string and str(string).strip():
                return [Token(word.strip(), 1.0, True)
                        for word in str(string).strip().split()
                        if word]
            else:
                return []

        # Our bindings etc.
        self._prefix = tokenize(prefix)
        self._bindings = {
            'Play'     : tokenize(play_key),
            'Stop'     : tokenize(stop_key),
            'Next'     : tokenize(next_key),
            'Previous' : tokenize(prev_key),
        }

        # The GLib main loop
        self._loop = None

        # And where we put the tokens
        self._output = []


    def read(self):
        """
        @see Input.read
        """
        if len(self._output) > 0:
            try:
                return self._output.pop()
            except:
                pass


    def _start(self):
        """
        @see Component.start()
        """
        # Configure the main loop. We use the GLib one here by default but we
        # could also look to use the QT one, dbus.mainloop.qt.DBusQtMainLoop, if
        # people need that. Mixing mainloop types between components (e.g. this
        # and NotifierOutput) can cause breakage.
        DBusGMainLoop()
        bus = dbus.Bus(dbus.Bus.TYPE_SESSION, mainloop=DBusGMainLoop())
        obj = bus.get_object('org.gnome.SettingsDaemon',
                             '/org/gnome/SettingsDaemon/MediaKeys')

        # How we get the media keys from the bus
        obj.GrabMediaPlayerKeys(
            self._APP,
            0,
            dbus_interface='org.gnome.SettingsDaemon.MediaKeys'
        )

        # Add the handler
        obj.connect_to_signal('MediaPlayerKeyPressed', self._on_key)

        # And start the main loop in its own thread
        self._loop = GLib.MainLoop()
        thread = Thread(name='MediaKeyMainLoop', target=self._loop.run)
        thread.daemon = True
        thread.start()


    def _stop(self):
       """
       @see Input.stop
       """
       try:
           if self._loop is not None:
               self._loop.quit()
               self._loop = None
       except:
           pass


    def _on_key(self, app, what):
        """
        Handle an incoming media key.
        """
        if app == self._APP:
            LOG.info("Got media key '%s'" % (what,))
            tokens = self._bindings.get(what, [])
            if len(tokens) > 0:
                self._output.append(tuple(self._prefix + tokens))
