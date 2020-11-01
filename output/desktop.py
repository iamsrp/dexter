"""
Output via desktop notifcations.
"""

# On Ubuntu 20.10, one of:
#    sudo apt install python3-notify2
#    pip3 install notify2

from   dexter.core.log import LOG
from   dexter.output   import Output

import logging
import notify2

# ------------------------------------------------------------------------------

class NotifierOutput(Output):
    """
    An output which sends responses as desktop noticications.
    """
    def __init__(self,
                 state,
                 summary   ='Dexter says:',
                 icon      ='im-message-new',
                 timeout_ms=10000,
                 loop_type ='glib'):
        """
        @see Output.__init__()
        
        :type  summary: str
        :param summary:
            What to put at the start of a notification, if anything.
        :type  icon: str
        :param icon:
            The name of the icon to use.
        :type  timeout_ms: int
        :param timeout_ms:
            The timeout, in millis, of the notification pop-ups.
        :type  loop_type: str
        :param loop_type:
            The DBus main loop type to use. Either ``glib`` or ``qt`` depending
            on your underlying windowing system. Also can be `None` for the 
            default. Note that using different DBus looptypes of different DBus
            components (e.g. MediaKeyInput) can result in breakage.
        """
        super(NotifierOutput, self).__init__(state)

        self._summary   = str(summary)    if summary    else None
        self._icon      = str(icon)       if icon       else None
        self._timeout   = int(timeout_ms) if timeout_ms else -1
        self._loop_type = str(loop_type)  if loop_type  else None

        try:
            notify2.init("Dexter", mainloop=self._loop_type)
        except Exception as e:
            LOG.warning("Failed to set up desktop notifications: %s" % e)


    def write(self, text):
        """
        @see Output.write
        """
        if text:
            try:
                n = notify2.Notification(self._summary,
                                         message=text,
                                         icon=self._icon)
                if self._timeout > 0:
                    n.set_timeout(self._timeout)
                n.show()

            except Exception as e:
                LOG.warning("Failed to display desktop notifications: %s" % e)

