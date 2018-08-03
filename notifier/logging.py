'''
A notifier which utilises the Unicorn Hat HD on a Raspberry Pi.

@see https://github.com/pimoroni/unicorn-hat-hd
'''

from __future__ import (absolute_import, division, print_function, with_statement)

from dexter.core     import Notifier
from dexter.core.log import LOG

# ------------------------------------------------------------------------------

class LogNotifier(Notifier):
    '''
    A notifier which just logs status changes.
    '''
    def update_status(self, component, status):
        '''
        @see Notifier.update_status()
        '''
        # Sanity
        if component is None or status is None:
            return

        LOG.info("Component %s is now %s", component, status)
