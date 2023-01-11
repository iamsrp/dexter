"""
Notifiers for the desktop.

On Raspberry Pi OS and Ubuntu::
  ``sudo apt-get install gir1.2-appindicator3``
"""

from   dexter.core     import Notifier
from   dexter.notifier import ByComponentNotifier
from   threading       import Thread

import time

# ------------------------------------------------------------------------------

class SysTrayNotifier(ByComponentNotifier):
    """
    A notifier which flags in the system tray.
    """
    def __init__(self, icon_name="user-available-symbolic"):
        """
        @see ByComponentNotifier.__init__()

        :type  icon_name: str
        :param icon_name:
            The name of the icon to use. On Ubuntu these can be found in the
            ``/usr/share/icons/.../scalable/status`` directories.
        """
        super(SysTrayNotifier, self).__init__()

        # Importing from GI requires some presetting
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import Gtk as gtk, AppIndicator3 as appindicator

        # Create the thing which will actually sit in the system tray
        self._indicator = appindicator.Indicator.new(
                              "customtray",
                              icon_name,
                              appindicator.IndicatorCategory.APPLICATION_STATUS
                          )

        # Save these so we can use them outside
        self._gtk = gtk
        self._active  = appindicator.IndicatorStatus.ACTIVE
        self._passive = appindicator.IndicatorStatus.PASSIVE

        # We start off passive
        self._indicator.set_status(self._passive)

        # We need at least one menu entry, even if it does nothing
        menu  = gtk.Menu()
        entry = gtk.MenuItem(label='Dexter')
        entry.connect('activate', lambda x: None)
        menu.append(entry)
        menu.show_all()
        self._indicator.set_menu(menu)


    def update_status(self, component, status):
        """
        @see Notifier.update_status()
        """
        # Sanity
        if component is None or status is None:
            return

        # See if the component has become idle or not, if it's not idle then we
        # show ourselves
        if status is Notifier.IDLE:
            self._indicator.set_status(self._passive)
        else:
            self._indicator.set_status(self._active)


    def _start(self):
        """
        @see Notifier._start()
        """
        # Not entirely sure if we need this or whether it will play nicely if we
        # have other gtk threads kicking about
        thread = Thread(name='DesktopNotifierMainLoop', target=self._gtk.main)
        thread.deamon = True
        thread.start()


    def _stop(self):
        """
        @see Notifier._start()
        """
        try:
            self._gtk.main_quit()
        except:
            # Best effort
            pass
