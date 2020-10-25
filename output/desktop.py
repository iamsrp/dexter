"""
Output via desktop notifcations.
"""

# On Ubuntu 20.10, one of:
#    sudo apt install python3-notify2
#    pip3 install notify2

import logging
import notify2

from   dexter.core.log import LOG
from   dexter.output   import Output

# ------------------------------------------------------------------------------

class NotifierOutput(Output):
    """
    An output which sends responses as desktop noticications.
    """
    def __init__(self,
                 state,
                 summary='Dexter says:',
                 icon='im-message-new',
                 timeout_ms=10000):
        """
        @see Output.__init__()
        """
        super(NotifierOutput, self).__init__(state)

        self._summary = str(summary)    if summary    else None
        self._icon    = str(icon)       if icon       else None
        self._timeout = int(timeout_ms) if timeout_ms else -1

        try:
            notify2.init("Dexter")
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
                
